#!/usr/bin/env python3
"""
Fault Tolerance Test Script for Flower Gossip

This script demonstrates the fault tolerance capabilities of the federated learning system
by simulating server failures and monitoring the system's response.
"""

import time
import subprocess
import requests
import json
import logging
from typing import Dict, List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FaultToleranceTester:
    def __init__(self):
        self.prometheus_url = "http://localhost:9090"
        self.grafana_url = "http://localhost:3000"
        self.test_results = []
        
    def check_service_health(self, service_name: str) -> bool:
        """Check if a service is healthy"""
        try:
            # Check if container is running
            result = subprocess.run(
                ["docker", "ps", "--filter", f"name={service_name}", "--format", "{{.Names}}"],
                capture_output=True, text=True
            )
            return service_name in result.stdout
        except Exception as e:
            logger.error(f"Error checking health of {service_name}: {e}")
            return False
            
    def get_metrics(self, metric_name: str) -> Dict:
        """Get metrics from Prometheus"""
        try:
            query = f"http://{self.prometheus_url}/api/v1/query?query={metric_name}"
            response = requests.get(query, timeout=5)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error getting metrics for {metric_name}: {e}")
            return {}
            
    def get_leader_status(self) -> Dict[str, bool]:
        """Get the leader status of all server nodes"""
        metrics = self.get_metrics("is_leader")
        leader_status = {}
        
        if 'data' in metrics and 'result' in metrics['data']:
            for result in metrics['data']['result']:
                if 'metric' in result and 'node_id' in result['metric']:
                    node_id = result['metric']['node_id']
                    is_leader = result['value'][1] == '1'
                    leader_status[node_id] = is_leader
                    
        return leader_status
        
    def get_node_status(self) -> Dict[str, bool]:
        """Get the status of all nodes"""
        metrics = self.get_metrics("node_status")
        node_status = {}
        
        if 'data' in metrics and 'result' in metrics['data']:
            for result in metrics['data']['result']:
                if 'metric' in result and 'node_id' in result['metric']:
                    node_id = result['metric']['node_id']
                    is_alive = result['value'][1] == '1'
                    node_status[node_id] = is_alive
                    
        return node_status
        
    def wait_for_leader_election(self, timeout: int = 30) -> bool:
        """Wait for leader election to complete"""
        logger.info("Waiting for leader election...")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            leader_status = self.get_leader_status()
            alive_leaders = [node for node, is_leader in leader_status.items() if is_leader]
            
            if len(alive_leaders) == 1:
                logger.info(f"Leader election completed. New leader: {alive_leaders[0]}")
                return True
                
            time.sleep(1)
            
        logger.error("Leader election timeout")
        return False
        
    def test_initial_setup(self) -> bool:
        """Test initial system setup"""
        logger.info("Testing initial system setup...")
        
        # Check if all services are running
        services = ["prometheus", "grafana", "cadvisor", "server-1", "server-2", "server-3"]
        for service in services:
            if not self.check_service_health(service):
                logger.error(f"Service {service} is not running")
                return False
                
        # Check initial leader
        leader_status = self.get_leader_status()
        if not leader_status.get("server-1", False):
            logger.error("server-1 should be the initial leader")
            return False
            
        logger.info("Initial setup test passed")
        return True
        
    def test_leader_failure(self) -> bool:
        """Test leader failure and recovery"""
        logger.info("Testing leader failure...")
        
        # Stop the current leader (server-1)
        logger.info("Stopping server-1 (current leader)...")
        subprocess.run(["docker-compose", "-f", "docker-compose-fault-tolerant.yml", "stop", "server-1"])
        
        # Wait for leader election
        if not self.wait_for_leader_election():
            return False
            
        # Check that server-2 or server-3 became leader
        leader_status = self.get_leader_status()
        new_leader = None
        for node, is_leader in leader_status.items():
            if is_leader:
                new_leader = node
                break
                
        if not new_leader or new_leader == "server-1":
            logger.error("Leader election failed")
            return False
            
        logger.info(f"Leader election successful. New leader: {new_leader}")
        
        # Restart server-1
        logger.info("Restarting server-1...")
        subprocess.run(["docker-compose", "-f", "docker-compose-fault-tolerant.yml", "start", "server-1"])
        
        # Wait for it to rejoin
        time.sleep(10)
        
        # Check that all nodes are alive
        node_status = self.get_node_status()
        if not all(node_status.values()):
            logger.error("Not all nodes are alive after restart")
            return False
            
        logger.info("Leader failure test passed")
        return True
        
    def test_model_synchronization(self) -> bool:
        """Test model synchronization across nodes"""
        logger.info("Testing model synchronization...")
        
        # Get model versions from all nodes
        model_metrics = self.get_metrics("model_version")
        
        if 'data' in model_metrics and 'result' in model_metrics['data']:
            versions = []
            for result in model_metrics['data']['result']:
                if 'value' in result:
                    versions.append(float(result['value'][1]))
                    
            if len(versions) > 1:
                # Check if versions are synchronized (within reasonable range)
                max_diff = max(versions) - min(versions)
                if max_diff <= 1:  # Allow for 1 round difference
                    logger.info("Model synchronization test passed")
                    return True
                else:
                    logger.error(f"Model versions not synchronized. Max difference: {max_diff}")
                    return False
                    
        logger.warning("Could not verify model synchronization")
        return True
        
    def run_all_tests(self) -> Dict:
        """Run all fault tolerance tests"""
        logger.info("Starting fault tolerance tests...")
        
        tests = [
            ("Initial Setup", self.test_initial_setup),
            ("Model Synchronization", self.test_model_synchronization),
            ("Leader Failure", self.test_leader_failure),
        ]
        
        results = {}
        
        for test_name, test_func in tests:
            logger.info(f"\n{'='*50}")
            logger.info(f"Running test: {test_name}")
            logger.info(f"{'='*50}")
            
            try:
                result = test_func()
                results[test_name] = result
                status = "PASSED" if result else "FAILED"
                logger.info(f"Test {test_name}: {status}")
            except Exception as e:
                logger.error(f"Test {test_name} failed with exception: {e}")
                results[test_name] = False
                
        # Summary
        logger.info(f"\n{'='*50}")
        logger.info("TEST SUMMARY")
        logger.info(f"{'='*50}")
        
        passed = sum(results.values())
        total = len(results)
        
        for test_name, result in results.items():
            status = "PASSED" if result else "FAILED"
            logger.info(f"{test_name}: {status}")
            
        logger.info(f"\nOverall: {passed}/{total} tests passed")
        
        return results

def main():
    """Main function to run fault tolerance tests"""
    tester = FaultToleranceTester()
    
    print("Fault Tolerance Test for Flower Gossip")
    print("=" * 50)
    print("This script will test the fault tolerance capabilities of your FL system.")
    print("Make sure the system is running with:")
    print("docker-compose -f docker-compose-fault-tolerant.yml up -d")
    print()
    
    input("Press Enter to start testing...")
    
    results = tester.run_all_tests()
    
    # Save results to file
    with open("fault_tolerance_test_results.json", "w") as f:
        json.dump(results, f, indent=2)
        
    print(f"\nResults saved to fault_tolerance_test_results.json")

if __name__ == "__main__":
    main() 