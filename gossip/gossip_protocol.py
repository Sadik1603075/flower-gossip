import asyncio
import json
import logging
import random
import time
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Dict, List, Optional, Set, Any
import threading
import socket
import pickle

logger = logging.getLogger(__name__)

class MessageType(Enum):
    HEARTBEAT = "heartbeat"
    MODEL_UPDATE = "model_update"
    LEADER_ELECTION = "leader_election"
    LEADER_ANNOUNCEMENT = "leader_announcement"
    CLIENT_REQUEST = "client_request"

@dataclass
class GossipMessage:
    message_type: MessageType
    sender_id: str
    timestamp: float
    data: dict
    sequence_number: int

@dataclass
class ServerNode:
    id: str
    host: str
    port: int
    is_alive: bool = True
    last_heartbeat: float = 0.0
    is_leader: bool = False

class GossipProtocol:
    def __init__(self, node_id: str, host: str, port: int, 
                 known_nodes: List[Dict[str, Any]], 
                 gossip_interval: float = 1.0,
                 failure_timeout: float = 5.0):
        self.node_id = node_id
        self.host = host
        self.port = port
        self.gossip_interval = gossip_interval
        self.failure_timeout = failure_timeout
        
        # Network state
        self.nodes: Dict[str, ServerNode] = {}
        self.known_nodes = known_nodes
        self.sequence_numbers: Dict[str, int] = {}
        self.received_messages: Set[str] = set()
        
        # Leader election state
        self.current_leader: Optional[str] = None
        self.election_in_progress = False
        self.leader_priority = int(node_id.split('-')[-1])  # server-1 has priority 1
        
        # Model state
        self.global_model = None
        self.model_version = 0
        
        # Threading
        self.running = False
        self.gossip_thread = None
        self.server_socket = None
        
        # Initialize nodes
        self._initialize_nodes()
        
    def _initialize_nodes(self):
        """Initialize the known nodes in the network"""
        for node_info in self.known_nodes:
            node = ServerNode(
                id=node_info['id'],
                host=node_info['host'],
                port=node_info['port'],
                is_leader=node_info.get('is_leader', False)
            )
            self.nodes[node.id] = node
            self.sequence_numbers[node.id] = 0
            
            if node.is_leader:
                self.current_leader = node.id
                
        # Add self to nodes
        self.nodes[self.node_id] = ServerNode(
            id=self.node_id,
            host=self.host,
            port=self.port,
            is_leader=self.node_id == self.current_leader
        )
        
    def start(self):
        """Start the gossip protocol"""
        self.running = True
        
        # Start UDP server for receiving messages
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.settimeout(1.0)
        
        # Start gossip thread
        self.gossip_thread = threading.Thread(target=self._gossip_loop)
        self.gossip_thread.daemon = True
        self.gossip_thread.start()
        
        # Start message receiver thread
        receiver_thread = threading.Thread(target=self._receive_messages)
        receiver_thread.daemon = True
        receiver_thread.start()
        
        logger.info(f"Gossip protocol started for node {self.node_id}")
        
    def stop(self):
        """Stop the gossip protocol"""
        self.running = False
        if self.server_socket:
            self.server_socket.close()
        logger.info(f"Gossip protocol stopped for node {self.node_id}")
        
    def _gossip_loop(self):
        """Main gossip loop - periodically sends heartbeats and processes failures"""
        while self.running:
            try:
                # Send heartbeat
                self._send_heartbeat()
                
                # Check for node failures
                self._check_node_failures()
                
                # Handle leader election if needed
                self._handle_leader_election()
                
                time.sleep(self.gossip_interval)
                
            except Exception as e:
                logger.error(f"Error in gossip loop: {e}")
                
    def _send_heartbeat(self):
        """Send heartbeat to random subset of nodes"""
        alive_nodes = [node for node in self.nodes.values() if node.id != self.node_id]
        if not alive_nodes:
            return
            
        # Select random subset of nodes (gossip factor)
        gossip_targets = random.sample(alive_nodes, min(2, len(alive_nodes)))
        
        message = GossipMessage(
            message_type=MessageType.HEARTBEAT,
            sender_id=self.node_id,
            timestamp=time.time(),
            data={"leader": self.current_leader, "model_version": self.model_version},
            sequence_number=self.sequence_numbers[self.node_id]
        )
        
        self._send_message(message, gossip_targets)
        self.sequence_numbers[self.node_id] += 1
        
    def _check_node_failures(self):
        """Check for failed nodes and trigger leader election if leader failed"""
        current_time = time.time()
        
        for node_id, node in self.nodes.items():
            if node_id == self.node_id:
                continue
                
            if current_time - node.last_heartbeat > self.failure_timeout:
                if node.is_alive:
                    logger.warning(f"Node {node_id} appears to have failed")
                    node.is_alive = False
                    
                    # If leader failed, start election
                    if node_id == self.current_leader:
                        logger.info("Leader failed, starting leader election")
                        self._start_leader_election()
                        
    def _start_leader_election(self):
        """Start a leader election process"""
        if self.election_in_progress:
            return
            
        self.election_in_progress = True
        self.current_leader = None
        
        # Send election message to all nodes
        message = GossipMessage(
            message_type=MessageType.LEADER_ELECTION,
            sender_id=self.node_id,
            timestamp=time.time(),
            data={"priority": self.leader_priority},
            sequence_number=self.sequence_numbers[self.node_id]
        )
        
        alive_nodes = [node for node in self.nodes.values() if node.is_alive and node.id != self.node_id]
        self._send_message(message, alive_nodes)
        self.sequence_numbers[self.node_id] += 1
        
    def _handle_leader_election(self):
        """Handle ongoing leader election"""
        if not self.election_in_progress:
            return
            
        # Simple leader election: highest priority wins
        highest_priority = max(
            [node for node in self.nodes.values() if node.is_alive],
            key=lambda x: int(x.id.split('-')[-1])
        )
        
        if highest_priority.id == self.node_id:
            self._announce_leader()
            
    def _announce_leader(self):
        """Announce self as the new leader"""
        self.current_leader = self.node_id
        self.election_in_progress = False
        
        # Update local state
        for node in self.nodes.values():
            node.is_leader = (node.id == self.node_id)
            
        # Announce to all nodes
        message = GossipMessage(
            message_type=MessageType.LEADER_ANNOUNCEMENT,
            sender_id=self.node_id,
            timestamp=time.time(),
            data={"leader_id": self.node_id},
            sequence_number=self.sequence_numbers[self.node_id]
        )
        
        alive_nodes = [node for node in self.nodes.values() if node.is_alive and node.id != self.node_id]
        self._send_message(message, alive_nodes)
        self.sequence_numbers[self.node_id] += 1
        
        logger.info(f"Node {self.node_id} is now the leader")
        
    def update_global_model(self, model_weights, version):
        """Update the global model and propagate to other nodes"""
        self.global_model = model_weights
        self.model_version = version
        
        # Send model update to other nodes
        message = GossipMessage(
            message_type=MessageType.MODEL_UPDATE,
            sender_id=self.node_id,
            timestamp=time.time(),
            data={"model_weights": model_weights, "version": version},
            sequence_number=self.sequence_numbers[self.node_id]
        )
        
        alive_nodes = [node for node in self.nodes.values() if node.is_alive and node.id != self.node_id]
        self._send_message(message, alive_nodes)
        self.sequence_numbers[self.node_id] += 1
        
    def _send_message(self, message: GossipMessage, targets: List[ServerNode]):
        """Send a message to target nodes"""
        message_data = {
            "message_type": message.message_type.value,
            "sender_id": message.sender_id,
            "timestamp": message.timestamp,
            "data": message.data,
            "sequence_number": message.sequence_number
        }
        
        serialized_message = pickle.dumps(message_data)
        
        for target in targets:
            try:
                if self.server_socket:
                    self.server_socket.sendto(serialized_message, (target.host, target.port))
            except Exception as e:
                logger.error(f"Failed to send message to {target.id}: {e}")
                
    def _receive_messages(self):
        """Receive and process incoming messages"""
        while self.running:
            try:
                if self.server_socket:
                    data, addr = self.server_socket.recvfrom(4096)
                    message_data = pickle.loads(data)
                
                message = GossipMessage(
                    message_type=MessageType(message_data["message_type"]),
                    sender_id=message_data["sender_id"],
                    timestamp=message_data["timestamp"],
                    data=message_data["data"],
                    sequence_number=message_data["sequence_number"]
                )
                
                self._process_message(message)
                
            except socket.timeout:
                continue
            except Exception as e:
                logger.error(f"Error receiving message: {e}")
                
    def _process_message(self, message: GossipMessage):
        """Process received message"""
        # Check if message already processed
        message_id = f"{message.sender_id}_{message.sequence_number}"
        if message_id in self.received_messages:
            return
            
        self.received_messages.add(message_id)
        
        # Update sender's heartbeat
        if message.sender_id in self.nodes:
            self.nodes[message.sender_id].last_heartbeat = time.time()
            self.nodes[message.sender_id].is_alive = True
            
        # Process based on message type
        if message.message_type == MessageType.HEARTBEAT:
            self._handle_heartbeat(message)
        elif message.message_type == MessageType.MODEL_UPDATE:
            self._handle_model_update(message)
        elif message.message_type == MessageType.LEADER_ELECTION:
            self._handle_leader_election_message(message)
        elif message.message_type == MessageType.LEADER_ANNOUNCEMENT:
            self._handle_leader_announcement(message)
            
    def _handle_heartbeat(self, message: GossipMessage):
        """Handle heartbeat message"""
        # Update leader information
        if "leader" in message.data:
            self.current_leader = message.data["leader"]
            
        # Update model version if newer
        if "model_version" in message.data and message.data["model_version"] > self.model_version:
            # Request model update from sender
            pass
            
    def _handle_model_update(self, message: GossipMessage):
        """Handle model update message"""
        if message.data["version"] > self.model_version:
            self.global_model = message.data["model_weights"]
            self.model_version = message.data["version"]
            logger.info(f"Updated global model to version {self.model_version}")
            
    def _handle_leader_election_message(self, message: GossipMessage):
        """Handle leader election message"""
        if not self.election_in_progress:
            return
            
        sender_priority = message.data["priority"]
        my_priority = self.leader_priority
        
        if sender_priority > my_priority:
            # Higher priority node exists, stop election
            self.election_in_progress = False
        elif sender_priority == my_priority and message.sender_id > self.node_id:
            # Same priority but higher ID, stop election
            self.election_in_progress = False
            
    def _handle_leader_announcement(self, message: GossipMessage):
        """Handle leader announcement message"""
        new_leader = message.data["leader_id"]
        self.current_leader = new_leader
        self.election_in_progress = False
        
        # Update node states
        for node in self.nodes.values():
            node.is_leader = (node.id == new_leader)
            
        logger.info(f"New leader announced: {new_leader}")
        
    def is_leader(self) -> bool:
        """Check if this node is the current leader"""
        return self.current_leader == self.node_id
        
    def get_global_model(self):
        """Get the current global model"""
        return self.global_model, self.model_version 