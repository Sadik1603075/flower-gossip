# Fault-Tolerant Federated Learning with Gossip Protocol

This implementation extends the Flower Gossip project with fault tolerance capabilities using a gossip protocol and leader election mechanism.

## 🏗️ Architecture Overview

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Server-1  │◄──►│   Server-2  │◄──►│   Server-3  │
│  (Master)   │    │ (Backup)    │    │ (Backup)    │
└─────────────┘    └─────────────┘    └─────────────┘
       ▲                   ▲                   ▲
       │                   │                   │
       ▼                   ▼                   ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Client-1   │    │  Client-2   │    │  Client-3   │
└─────────────┘    └─────────────┘    └─────────────┘
```

## 🎯 Key Features

### **Fault Tolerance**
- **Leader Election**: Automatic leader election when master fails
- **Model Synchronization**: Global model propagated via gossip protocol
- **Failure Detection**: Heartbeat-based failure detection
- **Automatic Recovery**: Seamless failover to backup servers

### **Gossip Protocol**
- **Decentralized Communication**: Peer-to-peer message exchange
- **Efficient Propagation**: Random subset messaging for scalability
- **Eventual Consistency**: Model updates eventually reach all nodes
- **Fault Isolation**: Node failures don't affect the entire system

### **Monitoring & Observability**
- **Real-time Metrics**: Leader status, node health, model versions
- **Prometheus Integration**: Comprehensive metrics collection
- **Grafana Dashboards**: Visual monitoring of system health
- **Fault Detection**: Automated failure detection and alerting

## 🚀 Quick Start

### **1. Generate Fault-Tolerant Configuration**

```bash
python helpers/generate_fault_tolerant_compose.py --total_clients 3 --num_rounds 50
```

This creates `docker-compose-fault-tolerant.yml` with:
- 3 server nodes (server-1, server-2, server-3)
- 3 FL clients
- Monitoring stack (Prometheus, Grafana, cAdvisor)

### **2. Start the System**

```bash
docker-compose -f docker-compose-fault-tolerant.yml up -d
```

### **3. Monitor the System**

- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000
- **Server Metrics**: 
  - server-1: http://localhost:8001/metrics
  - server-2: http://localhost:8002/metrics
  - server-3: http://localhost:8003/metrics

### **4. Test Fault Tolerance**

```bash
python test_fault_tolerance.py
```

This script will:
- Test initial system setup
- Simulate leader failure
- Verify automatic recovery
- Check model synchronization

## 🔧 Configuration

### **Server Configuration**

Each server node runs with:
- **FL Server Port**: 8080, 8081, 8082 (for client communication)
- **Gossip Port**: 9001, 9002, 9003 (for inter-node communication)
- **Metrics Port**: 8000 (for Prometheus monitoring)

### **Leader Election**

- **Initial Leader**: server-1 (highest priority)
- **Election Algorithm**: Priority-based (server-1 > server-2 > server-3)
- **Failure Timeout**: 5 seconds
- **Heartbeat Interval**: 1 second

### **Gossip Protocol**

- **Message Types**: Heartbeat, Model Update, Leader Election, Leader Announcement
- **Gossip Factor**: 2 (send to 2 random nodes)
- **Sequence Numbers**: Prevent duplicate message processing
- **UDP Communication**: Lightweight, fast propagation

## 📊 Monitoring Metrics

### **Prometheus Metrics**

```yaml
# Leader Status
is_leader{node_id="server-1"} 1

# Node Health
node_status{node_id="server-1"} 1
node_status{node_id="server-2"} 1
node_status{node_id="server-3"} 0  # Failed node

# Model Performance
model_accuracy 0.85
model_loss 0.15
```

### **Grafana Dashboards**

1. **System Overview**
   - Node status and health
   - Current leader
   - Model performance metrics

2. **Fault Tolerance**
   - Leader election events
   - Node failure detection
   - Recovery time metrics

3. **Training Progress**
   - Model accuracy over time
   - Loss convergence
   - Round completion status

## 🧪 Testing Scenarios

### **1. Normal Operation**
```bash
# Start system
docker-compose -f docker-compose-fault-tolerant.yml up -d

# Monitor leader election
curl http://localhost:9090/api/v1/query?query=is_leader
```

### **2. Leader Failure**
```bash
# Stop the leader
docker-compose -f docker-compose-fault-tolerant.yml stop server-1

# Wait for election (5-10 seconds)
# Check new leader
curl http://localhost:9090/api/v1/query?query=is_leader
```

### **3. Leader Recovery**
```bash
# Restart the failed leader
docker-compose -f docker-compose-fault-tolerant.yml start server-1

# Verify it rejoins as backup
curl http://localhost:9090/api/v1/query?query=node_status
```

### **4. Multiple Failures**
```bash
# Stop multiple nodes
docker-compose -f docker-compose-fault-tolerant.yml stop server-1 server-2

# Verify remaining node becomes leader
# Restart nodes and verify recovery
```

## 🔍 Troubleshooting

### **Common Issues**

1. **Leader Election Not Working**
   - Check gossip ports (9001, 9002, 9003)
   - Verify network connectivity between nodes
   - Check logs: `docker logs server-1`

2. **Model Not Synchronizing**
   - Verify gossip protocol is running
   - Check model version metrics
   - Ensure leader is performing aggregation

3. **Clients Can't Connect**
   - Verify FL server ports (8080, 8081, 8082)
   - Check client configuration points to correct leader
   - Verify leader is active

### **Debug Commands**

```bash
# Check node status
docker ps --filter "name=server"

# View logs
docker logs server-1
docker logs server-2
docker logs server-3

# Check metrics
curl http://localhost:8001/metrics | grep -E "(is_leader|node_status)"

# Test gossip communication
docker exec server-1 ping server-2
```

## 📈 Performance Considerations

### **Scalability**
- **Gossip Factor**: Configurable for different network sizes
- **Heartbeat Interval**: Adjustable based on network latency
- **Failure Timeout**: Balance between responsiveness and stability

### **Resource Usage**
- **Memory**: ~2GB per server node
- **CPU**: 2-4 cores per node
- **Network**: Minimal overhead for gossip messages

### **Optimization Tips**
- Use dedicated network for gossip communication
- Monitor gossip message frequency
- Adjust failure detection timeouts based on environment

## 🔮 Future Enhancements

1. **Dynamic Membership**: Add/remove nodes without restart
2. **Consensus Protocol**: Implement Raft or Paxos for stronger consistency
3. **Load Balancing**: Distribute client connections across nodes
4. **Geographic Distribution**: Support multi-region deployments
5. **Advanced Monitoring**: Custom Grafana dashboards for FL metrics

## 📚 References

- [Flower Framework Documentation](https://flower.dev/)
- [Gossip Protocol Overview](https://en.wikipedia.org/wiki/Gossip_protocol)
- [Federated Learning Survey](https://arxiv.org/abs/1908.07873)
- [Distributed Systems Principles](https://www.distributed-systems.net/)

## 🤝 Contributing

To contribute to the fault tolerance implementation:

1. Fork the repository
2. Create a feature branch
3. Implement your changes
4. Add tests for new functionality
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details. 