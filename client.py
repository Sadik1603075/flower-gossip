import argparse
import logging
import os
import time  # ← Add this import for time.sleep()

import flwr as fl
import tensorflow as tf
from helpers.load_data import load_data

from model.model import Model

logging.basicConfig(level=logging.INFO)  # Configure logging
logger = logging.getLogger(__name__)  # Create logger for the module

# Make TensorFlow log less verbose
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

# Parse command line arguments
parser = argparse.ArgumentParser(description="Flower client")

parser.add_argument(
    "--server_address", type=str, default="server:8080", help="Address of the server"
)
parser.add_argument(
    "--batch_size", type=int, default=32, help="Batch size for training"
)
parser.add_argument(
    "--learning_rate", type=float, default=0.1, help="Learning rate for the optimizer"
)
parser.add_argument("--client_id", type=int, default=1, help="Unique ID for the client")
parser.add_argument(
    "--total_clients", type=int, default=2, help="Total number of clients"
)
parser.add_argument(
    "--data_percentage", type=float, default=0.5, help="Portion of client data to use"
)

args = parser.parse_args()

# Create an instance of the model and pass the learning rate as an argument
model = Model(learning_rate=args.learning_rate)

# Compile the model
model.compile()


class Client(fl.client.NumPyClient):
    def __init__(self, args):
        self.args = args

        logger.info("Preparing data...")
        (x_train, y_train), (x_test, y_test) = load_data(
            data_sampling_percentage=self.args.data_percentage,
            client_id=self.args.client_id,
            total_clients=self.args.total_clients,
        )

        self.x_train = x_train
        self.y_train = y_train
        self.x_test = x_test
        self.y_test = y_test

    def get_parameters(self, config):
        # Return the parameters of the model
        return model.get_model().get_weights()

    def fit(self, parameters, config):
        # Set the weights of the model
        model.get_model().set_weights(parameters)

        # Train the model
        history = model.get_model().fit(
            self.x_train, self.y_train, batch_size=self.args.batch_size
        )

        # Calculate evaluation metric
        results = {
            "accuracy": float(history.history["accuracy"][-1]),
            "loss": float(history.history["loss"][-1]),  # Add loss
        }

        # Get the parameters after training
        parameters_prime = model.get_model().get_weights()

        # Directly return the parameters and the number of examples trained on
        return parameters_prime, len(self.x_train), results

    def evaluate(self, parameters, config):
        # Set the weights of the model
        model.get_model().set_weights(parameters)

        # Evaluate the model and get the loss and accuracy
        loss, accuracy = model.get_model().evaluate(
            self.x_test, self.y_test, batch_size=self.args.batch_size
        )

        # Return the loss, the number of examples evaluated on and the accuracy
        return float(loss), len(self.x_test), {"accuracy": float(accuracy)}


def get_available_server():
    """Try to connect to available servers in order of priority"""
    servers = [
        "server-1:8080",  # Primary
        "server-2:8081",  # Secondary  
        "server-3:8082"   # Tertiary
    ]
    
    for server in servers:
        try:
            # Try to connect
            logger.info(f"Attempting to connect to {server}")
            # Test connection here
            return server
        except Exception as e:
            logger.warning(f"Failed to connect to {server}: {e}")
            continue
    
    raise Exception("No servers available")

# Function to Start the Client
def start_fl_client():
    max_retries = 3
    retry_delay = 5
    
    for attempt in range(max_retries):
        try:
            server_address = get_available_server()
            logger.info(f"Attempt {attempt + 1}: Connecting to {server_address}")
            
            client = Client(args).to_client()
            fl.client.start_client(server_address=server_address, client=client)
            break
            
        except Exception as e:
            logger.error(f"Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                logger.error("All connection attempts failed")
                return {"status": "error", "message": "No servers available"}


if __name__ == "__main__":
    # Call the function to start the client
    start_fl_client()
