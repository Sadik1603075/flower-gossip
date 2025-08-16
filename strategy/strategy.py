import logging
from typing import Dict, List, Optional, Tuple, Union
import flwr as fl
from flwr.common import EvaluateRes, Scalar
from flwr.server.client_proxy import ClientProxy
from flwr.server.strategy.aggregate import aggregate, weighted_loss_avg
from prometheus_client import Gauge

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class FaultTolerantStrategy(fl.server.strategy.FedAvg):
    def __init__(self, gossip, accuracy_gauge: Gauge = None, loss_gauge: Gauge = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.gossip = gossip
        self.accuracy_gauge = accuracy_gauge
        self.loss_gauge = loss_gauge

    def aggregate_fit(
        self, server_round: int, results: List[Tuple[ClientProxy, fl.common.FitRes]], failures
    ):
        if not self.gossip.is_leader():
            logger.info(f"Node {self.gossip.node_id} is not leader, skipping fit aggregation")
            return None, {}

        if not results:
            logger.warning(f"No client results received for round {server_round}")
            return None, {}

        # Aggregate parameters
        aggregated_parameters, _ = super().aggregate_fit(server_round, results, failures)

        if aggregated_parameters:
            # Update gossip global model
            self.gossip.update_global_model(aggregated_parameters, server_round)
            logger.info(f"Round {server_round}: Updated global model version {server_round}")
            
            # Update metrics from training results if available
            if results and hasattr(results[0][1], 'metrics') and 'accuracy' in results[0][1].metrics:
                accuracies = [res.metrics["accuracy"] * res.num_examples for _, res in results]
                examples = [res.num_examples for _, res in results]
                accuracy_aggregated = sum(accuracies) / sum(examples) if sum(examples) else 0
                
                if self.accuracy_gauge:
                    self.accuracy_gauge.set(accuracy_aggregated)
                logger.info(f"Round {server_round}: Training Accuracy {accuracy_aggregated:.4f}")

        return aggregated_parameters, {}

    def aggregate_evaluate(
        self, server_round: int, results: List[Tuple[ClientProxy, EvaluateRes]], failures
    ) -> Tuple[Optional[float], Dict[str, Scalar]]:
        if not self.gossip.is_leader():
            logger.info(f"Node {self.gossip.node_id} is not leader, skipping evaluation aggregation")
            return None, {}

        if not results:
            logger.warning(f"No client evaluation results received for round {server_round}")
            return None, {}

        # Weighted average loss
        loss_aggregated = weighted_loss_avg(
            [(res.num_examples, res.loss) for _, res in results]
        )

        # Weighted average accuracy
        accuracies = [res.metrics["accuracy"] * res.num_examples for _, res in results]
        examples = [res.num_examples for _, res in results]
        accuracy_aggregated = sum(accuracies) / sum(examples) if sum(examples) else 0

        # Update Prometheus metrics
        if self.accuracy_gauge:
            self.accuracy_gauge.set(accuracy_aggregated)
        if self.loss_gauge:
            self.loss_gauge.set(loss_aggregated)

        logger.info(f"Round {server_round}: Aggregated Accuracy {accuracy_aggregated:.4f}, Loss {loss_aggregated:.4f}")

        return loss_aggregated, {"accuracy": accuracy_aggregated, "loss": loss_aggregated}

    def configure_fit(self, server_round: int, parameters, client_manager):
        """Send latest global model to clients"""
        latest_model, latest_version = self.gossip.get_global_model()
        if latest_model is not None:
            logger.debug(f"Sending global model version {latest_version} to clients")
            parameters = latest_model
        return super().configure_fit(server_round, parameters, client_manager)

    def configure_evaluate(self, server_round: int, parameters, client_manager):
        """Send latest model to clients for evaluation"""
        latest_model, latest_version = self.gossip.get_global_model()
        if latest_model is not None:
            parameters = latest_model
        return super().configure_evaluate(server_round, parameters, client_manager)
