import argparse
import random

parser = argparse.ArgumentParser(description="Generate Fault-Tolerant Docker Compose")
parser.add_argument(
    "--total_clients", type=int, default=3, help="Total clients to spawn (default: 3)"
)
parser.add_argument(
    "--num_rounds", type=int, default=50, help="Number of FL rounds (default: 50)"
)
parser.add_argument(
    "--data_percentage",
    type=float,
    default=0.6,
    help="Portion of client data to use (default: 0.6)",
)
parser.add_argument(
    "--random", action="store_true", help="Randomize client configurations"
)


def create_fault_tolerant_compose(args):
    # Client configurations for heterogeneity
    client_configs = [
        {"mem_limit": "3g", "batch_size": 32, "cpus": 4, "learning_rate": 0.001},
        {"mem_limit": "6g", "batch_size": 256, "cpus": 1, "learning_rate": 0.05},
        {"mem_limit": "4g", "batch_size": 64, "cpus": 3, "learning_rate": 0.02},
        {"mem_limit": "5g", "batch_size": 128, "cpus": 2.5, "learning_rate": 0.09},
    ]

    docker_compose_content = f"""
version: '3.8'

services:
  # Monitoring Stack
  prometheus:
    image: prom/prometheus:latest
    container_name: prometheus
    ports:
      - 9090:9090
    deploy:
      restart_policy:
        condition: on-failure
    command:
      - --config.file=/etc/prometheus/prometheus.yml
    volumes:
      - ./config/prometheus.yml:/etc/prometheus/prometheus.yml:ro
    depends_on:
      - cadvisor

  cadvisor:
    image: gcr.io/cadvisor/cadvisor:v0.47.0
    container_name: cadvisor
    privileged: true
    deploy:
      restart_policy:
        condition: on-failure
    ports:
      - "8080:8080"
    volumes:
      - /:/rootfs:ro
      - /var/run:/var/run:ro
      - /sys:/sys:ro
      - /var/lib/docker/:/var/lib/docker:ro
      - /dev/disk/:/dev/disk:ro
      - /var/run/docker.sock:/var/run/docker.sock

  grafana:
    image: grafana/grafana:latest
    container_name: grafana
    ports:
      - 3000:3000
    deploy:
      restart_policy:
        condition: on-failure
    volumes:
      - grafana-storage:/var/lib/grafana
      - ./config/grafana.ini:/etc/grafana/grafana.ini
      - ./config/provisioning/datasources:/etc/grafana/provisioning/datasources
      - ./config/provisioning/dashboards:/etc/grafana/provisioning/dashboards
    depends_on:
      - prometheus
      - cadvisor
    command:
      - --config=/etc/grafana/grafana.ini

  # Fault-Tolerant Server Nodes
  server-1:
    container_name: server-1
    build:
      context: .
      dockerfile: Dockerfile
    command: python fault_tolerant_server.py --node_id=server-1 --port=8080 --gossip_port=9001 --num_rounds={args.num_rounds}
    environment:
      FLASK_RUN_PORT: 6000
      DOCKER_HOST_IP: host.docker.internal
    volumes:
      - .:/app
      - /var/run/docker.sock:/var/run/docker.sock
    ports:
      - "6000:6000"
      - "8080:8080"
      - "8001:8000"
      - "9001:9001"
    stop_signal: SIGINT
    depends_on:
      - prometheus
      - grafana
    deploy:
      restart_policy:
        condition: on-failure

  server-2:
    container_name: server-2
    build:
      context: .
      dockerfile: Dockerfile
    command: python fault_tolerant_server.py --node_id=server-2 --port=8081 --gossip_port=9002 --num_rounds={args.num_rounds}
    environment:
      FLASK_RUN_PORT: 6001
      DOCKER_HOST_IP: host.docker.internal
    volumes:
      - .:/app
      - /var/run/docker.sock:/var/run/docker.sock
    ports:
      - "6001:6001"
      - "8081:8081"
      - "8002:8000"
      - "9002:9002"
    stop_signal: SIGINT
    depends_on:
      - prometheus
      - grafana
    deploy:
      restart_policy:
        condition: on-failure

  server-3:
    container_name: server-3
    build:
      context: .
      dockerfile: Dockerfile
    command: python fault_tolerant_server.py --node_id=server-3 --port=8082 --gossip_port=9003 --num_rounds={args.num_rounds}
    environment:
      FLASK_RUN_PORT: 6002
      DOCKER_HOST_IP: host.docker.internal
    volumes:
      - .:/app
      - /var/run/docker.sock:/var/run/docker.sock
    ports:
      - "6002:6002"
      - "8082:8082"
      - "8003:8000"
      - "9003:9003"
    stop_signal: SIGINT
    depends_on:
      - prometheus
      - grafana
    deploy:
      restart_policy:
        condition: on-failure
"""

    # Add client services
    for i in range(1, args.total_clients + 1):
        if args.random:
            config = random.choice(client_configs)
        else:
            config = client_configs[(i - 1) % len(client_configs)]
            
        docker_compose_content += f"""
  client{i}:
    container_name: client{i}
    build:
      context: .
      dockerfile: Dockerfile
    command: python client.py --server_address=server-1:8080 --data_percentage={args.data_percentage} --client_id={i} --total_clients={args.total_clients} --batch_size={config["batch_size"]} --learning_rate={config["learning_rate"]}
    deploy:
      resources:
        limits:
          cpus: "{(config['cpus'])}"
          memory: "{config['mem_limit']}"
    volumes:
      - .:/app
      - /var/run/docker.sock:/var/run/docker.sock
    ports:
      - "{7000 + i}:{7000 + i}"
    depends_on:
      - server-1
      - server-2
      - server-3
    environment:
      FLASK_RUN_PORT: {7000 + i}
      container_name: client{i}
      DOCKER_HOST_IP: host.docker.internal
    stop_signal: SIGINT
"""

    docker_compose_content += "volumes:\n  grafana-storage:\n"

    with open("docker-compose-fault-tolerant.yml", "w") as file:
        file.write(docker_compose_content)
        
    print("Generated docker-compose-fault-tolerant.yml")
    print(f"Configuration: {args.total_clients} clients, {args.num_rounds} rounds, {args.data_percentage*100}% data usage")
    print("\nTo start the fault-tolerant system:")
    print("docker-compose -f docker-compose-fault-tolerant.yml up -d")
    print("\nTo test fault tolerance:")
    print("docker-compose -f docker-compose-fault-tolerant.yml stop server-1")


if __name__ == "__main__":
    args = parser.parse_args()
    create_fault_tolerant_compose(args) 