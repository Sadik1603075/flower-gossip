# 🖥️ Multi-Laptop Fault-Tolerant FL Setup

This setup distributes your fault-tolerant federated learning system across 3 laptops using Docker containers.

## 📍 **Laptop Configuration**

| Laptop | IP Address | Services | Ports |
|--------|------------|----------|-------|
| **Laptop 1** | 192.168.1.14 | Prometheus + Grafana + Server-1 + Client-1 | 9090, 3000, 8080, 8001, 9001 |
| **Laptop 2** | 192.168.1.12 | Server-2 + Client-2 | 8081, 8002, 9002 |
| **Laptop 3** | 192.168.1.13 | Server-3 + Client-3 | 8082, 8003, 9003 |

## 🚀 **Setup Instructions**

### **Prerequisites**
- Docker installed on all 3 laptops
- All laptops connected to the same network (192.168.1.x)
- Firewall ports open for the required services

### **Step 1: Copy Files to Each Laptop**
Copy the entire project folder to each laptop, or ensure they can access the same codebase.

### **Step 2: Start Services on Each Laptop**

#### **Laptop 1 (192.168.1.14) - Monitoring + Server-1**
```bash
# Start Prometheus, Grafana, Server-1, and Client-1
docker-compose -f docker-compose-laptop1.yml up -d

# Check status
docker-compose -f docker-compose-laptop1.yml ps

# View logs
docker logs server-1
docker logs client1
```

#### **Laptop 2 (192.168.1.12) - Server-2**
```bash
# Start Server-2 and Client-2
docker-compose -f docker-compose-laptop2.yml up -d

# Check status
docker-compose -f docker-compose-laptop2.yml ps

# View logs
docker logs server-2
docker logs client2
```

#### **Laptop 3 (192.168.1.13) - Server-3**
```bash
# Start Server-3 and Client-3
docker-compose -f docker-compose-laptop3.yml up -d

# Check status
docker-compose -f docker-compose-laptop3.yml ps

# View logs
docker logs server-3
docker logs client3
```

## 🌐 **Access Points**

### **Laptop 1 (192.168.1.14)**
- **Prometheus**: http://192.168.1.14:9090
- **Grafana**: http://192.168.1.14:3000
- **Server-1 FL**: http://192.168.1.14:8080
- **Server-1 Metrics**: http://192.168.1.14:8001
- **Server-1 Gossip**: 192.168.1.14:9001

### **Laptop 2 (192.168.1.12)**
- **Server-2 FL**: http://192.168.1.12:8081
- **Server-2 Metrics**: http://192.168.1.12:8002
- **Server-2 Gossip**: 192.168.1.12:9002

### **Laptop 3 (192.168.1.13)**
- **Server-3 FL**: http://192.168.1.13:8082
- **Server-3 Metrics**: http://192.168.1.13:8003
- **Server-3 Gossip**: 192.168.1.13:9003

## 🔧 **Troubleshooting**

### **Check Network Connectivity**
```bash
# From Laptop 1, test connectivity to others
ping 192.168.1.12
ping 192.168.1.13

# Test specific ports
telnet 192.168.1.12 8002  # Server-2 metrics
telnet 192.168.1.13 8003  # Server-3 metrics
```

### **Check Container Status**
```bash
# On each laptop
docker ps
docker logs <container-name>
```

### **Common Issues**
1. **Firewall blocking ports**: Ensure ports 8001-8003, 9001-9003 are open
2. **Network isolation**: Verify all laptops are on the same subnet
3. **Docker network**: Check if Docker containers can reach external IPs

## 📊 **Monitoring**

### **Prometheus Targets**
- Navigate to http://192.168.1.14:9090/targets
- Verify all 3 servers are showing as "UP"

### **Grafana Dashboards**
- Access http://192.168.1.14:3000
- Default credentials: admin/admin
- Import the provided dashboards for FL metrics

## 🛑 **Stopping Services**

### **Stop All Services**
```bash
# On each laptop
docker-compose -f docker-compose-laptop<X>.yml down
```

### **Clean Up**
```bash
# Remove all containers and images (optional)
docker system prune -a
```

## 📝 **Notes**

- **Gossip Protocol**: Servers communicate via UDP on ports 9001-9003
- **Metrics Collection**: Prometheus scrapes metrics from all 3 servers every 1 second
- **Fault Tolerance**: If any server fails, the gossip protocol will detect and handle it
- **Load Balancing**: Clients connect to their local server, but the FL protocol aggregates across all servers
