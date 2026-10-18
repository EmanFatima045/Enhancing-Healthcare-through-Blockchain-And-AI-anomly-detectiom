"""
HealerPlus 2.0 - Privacy-Preserving Federated Learning Engine
Simulates cross-hospital collaborative model training using Federated Averaging (FedAvg).
Allows multiple hospital nodes (e.g., Hospital Bahawalpur, Mayo Hospital, Shaukat Khanum)
to train local threat detection weights without sharing sensitive patient or network logs.
"""

import copy
import random
import time
from typing import Dict, List, Any

class HospitalNode:
    def __init__(self, node_id: str, name: str, local_samples: int):
        self.node_id = node_id
        self.name = name
        self.local_samples = local_samples
        # Simulated model weights (representing dense layer weights for anomaly classification)
        self.local_weights = [
            random.uniform(0.4, 0.6) for _ in range(8)
        ]
        self.local_loss = random.uniform(0.25, 0.45)
        self.local_accuracy = random.uniform(0.88, 0.94)

    def local_train(self, global_weights: List[float], epochs: int = 3) -> Dict[str, Any]:
        """
        Trains locally initialized from global model weights
        """
        # Adopt global weights
        self.local_weights = copy.deepcopy(global_weights)

        # Simulate gradient descent update
        learning_rate = 0.05
        for _ in range(epochs):
            for i in range(len(self.local_weights)):
                noise = random.uniform(-0.02, 0.02)
                gradient = (self.local_weights[i] - 0.5) * 0.1 + noise
                self.local_weights[i] -= learning_rate * gradient

        # Update metrics
        self.local_loss = max(0.04, self.local_loss * 0.88 + random.uniform(-0.01, 0.01))
        self.local_accuracy = min(0.992, self.local_accuracy + (1.0 - self.local_accuracy) * 0.22)

        return {
            "node_id": self.node_id,
            "name": self.name,
            "samples_contributed": self.local_samples,
            "weights": self.local_weights,
            "loss": round(self.local_loss, 4),
            "accuracy": round(self.local_accuracy, 4)
        }

class FederatedCoordinator:
    def __init__(self):
        self.round_number = 0
        self.global_weights = [0.5] * 8
        self.global_accuracy = 0.895
        self.global_loss = 0.380
        self.training_history: List[Dict[str, Any]] = []

        # Simulated participating healthcare institutions
        self.nodes = [
            HospitalNode("node-01", "Bahawal Victoria Hospital (IUB Node)", 450),
            HospitalNode("node-02", "Sheikh Zayed Medical Center (Rahim Yar Khan)", 380),
            HospitalNode("node-03", "Nishtar Hospital Node (Multan)", 520),
            HospitalNode("node-04", "National Central Cyber-Health Node (Islamabad)", 600),
        ]

    def run_federated_round(self, epochs: int = 3) -> Dict[str, Any]:
        """
        Executes one round of Federated Averaging (FedAvg):
        1. Distributes global model to all hospital clients.
        2. Clients train locally on private threat logs.
        3. Aggregates weight updates using sample-weighted averaging.
        """
        self.round_number += 1
        node_updates = []
        total_samples = sum(n.local_samples for n in self.nodes)

        # 1. Local client updates
        for node in self.nodes:
            update = node.local_train(self.global_weights, epochs=epochs)
            node_updates.append(update)

        # 2. FedAvg Aggregation
        new_global_weights = [0.0] * len(self.global_weights)
        weighted_loss = 0.0
        weighted_acc = 0.0

        for update in node_updates:
            weight_factor = update["samples_contributed"] / total_samples
            for i in range(len(new_global_weights)):
                new_global_weights[i] += update["weights"][i] * weight_factor
            weighted_loss += update["loss"] * weight_factor
            weighted_acc += update["accuracy"] * weight_factor

        self.global_weights = new_global_weights
        self.global_loss = round(weighted_loss, 4)
        self.global_accuracy = round(weighted_acc, 4)

        round_result = {
            "round": self.round_number,
            "timestamp": time.time(),
            "participating_nodes": len(self.nodes),
            "total_samples": total_samples,
            "global_accuracy": self.global_accuracy,
            "global_loss": self.global_loss,
            "node_updates": node_updates,
            "privacy_guarantee": None,
            "simulation": True,
            "real_hospitals_connected": 0,
        }

        self.training_history.append(round_result)
        return round_result

    def get_status(self) -> Dict[str, Any]:
        return {
            "current_round": self.round_number,
            "global_accuracy": self.global_accuracy,
            "global_loss": self.global_loss,
            "nodes_count": len(self.nodes),
            "nodes": [{"id": n.node_id, "name": n.name, "samples": n.local_samples} for n in self.nodes],
            "history": self.training_history[-10:] # Last 10 rounds
        }

# Global singleton
fed_coordinator = FederatedCoordinator()
