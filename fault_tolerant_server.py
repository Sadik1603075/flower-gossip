import argparse
import logging
import os
import signal
import sys
import time
from typing import Dict, List, Optional

import flwr as fl
import numpy as np

from prometheus_client import Gauge, start_http_server
from strategy.strategy import FaultTolerantStrategy
from gossip.gossip_protocol import GossipProtocol

# Initialize Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define Prometheus gauges
accuracy_gauge = Gauge("model_accuracy", "Current accuracy of the global model")
loss_gauge = Gauge("model_loss", "Current loss of the global model")
leader_gauge = Gauge("is_leader", "Whether this node is the current leader")
node_status_gauge = Gauge("node_status", "Status of nodes in the cluster", ["node_id"])

class FaultTolerantServer:
    def __init__(self, node_id: str, host: str, port: int, 
                 gossip_port: int, known_nodes: List[Dict], 
                 num_rounds: int = 100):
        self.node_id = node_id
        self.host = host
        self.port = port
        self.gossip_port = gossip_port
        self.num_rounds = num_rounds
        
        # Initialize gossip protocol
        self.gossip = GossipProtocol(
            node_id=node_id,
            host=host,
            port=gossip_port,
            known_nodes=known_nodes
        )
        
        # FL state
        self.current_round = 0
        self.global_model = None
        self.model_version = 0
        
        # Strategy with fault tolerance
        self.strategy = FaultTolerantStrategy(
            gossip=self.gossip,  # Fix parameter order
            accuracy_gauge=accuracy_gauge,
            loss_gauge=loss_gauge
        )
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.stop()
        sys.exit(0)
        
    def start(self):
        """Start the fault-tolerant server"""
        try:
            # Start Prometheus metrics server
            start_http_server(8000)
            
            # Start gossip protocol
            self.gossip.start()
            
            # Update node status
            self._update_node_status()
            
            # Start FL server
            logger.info(f"Starting fault-tolerant FL server {self.node_id}")
            fl.server.start_server(
                server_address=f"{self.host}:{self.port}",
                config=fl.server.ServerConfig(num_rounds=self.num_rounds),
                strategy=self.strategy,
            )
            
        except Exception as e:
            logger.error(f"Error starting fault-tolerant server: {e}", exc_info=True)
            self.stop()
            raise
            
    def stop(self):
        """Stop the fault-tolerant server"""
        logger.info(f"Stopping fault-tolerant server {self.node_id}")
        if self.gossip:
            self.gossip.stop()
            
    def _update_node_status(self):
        """Update Prometheus metrics for node status"""
        # Update leader status
        leader_gauge.set(1 if self.gossip.is_leader() else 0)
        
        # Update node status for all nodes
        for node_id, node in self.gossip.nodes.items():
            node_status_gauge.labels(node_id=node_id).set(1 if node.is_alive else 0)



def main():
    parser = argparse.ArgumentParser(description="Fault-Tolerant Flower Server")
    parser.add_argument("--node_id", type=str, required=True, help="Unique node ID (e.g., server-1)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8080, help="FL server port")
    parser.add_argument("--gossip_port", type=int, required=True, help="Gossip protocol port")
    parser.add_argument("--num_rounds", type=int, default=100, help="Number of FL rounds")
    
    args = parser.parse_args()
    
    # Define the cluster configuration
    # This should match the configuration used in docker-compose
    known_nodes = [
        {
            "id": "server-1",
            "host": "server-1",
            "port": 9001,
            "is_leader": True  # server-1 starts as leader
        },
        {
            "id": "server-2", 
            "host": "server-2",
            "port": 9002,
            "is_leader": False
        },
        {
            "id": "server-3",
            "host": "server-3", 
            "port": 9003,
            "is_leader": False
        }
    ]
    
    # Create and start fault-tolerant server
    server = FaultTolerantServer(
        node_id=args.node_id,
        host=args.host,
        port=args.port,
        gossip_port=args.gossip_port,
        known_nodes=known_nodes,
        num_rounds=args.num_rounds
    )
    
    try:
        server.start()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    finally:
        server.stop()

if __name__ == "__main__":
    main() 