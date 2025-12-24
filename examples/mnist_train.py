"""
MNIST Training Example for ComputeSwarm
Demonstrates a realistic ML training job
"""

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset

# Simple CNN model
class SimpleCNN(nn.Module):
    def __init__(self):
        super(SimpleCNN, self).__init__()
        self.conv1 = nn.Conv2d(1, 32, kernel_size=3, padding=1)
        self.conv2 = nn.Conv2d(32, 64, kernel_size=3, padding=1)
        self.fc1 = nn.Linear(64 * 7 * 7, 128)
        self.fc2 = nn.Linear(128, 10)
        self.pool = nn.MaxPool2d(2, 2)
        self.relu = nn.ReLU()

    def forward(self, x):
        x = self.pool(self.relu(self.conv1(x)))
        x = self.pool(self.relu(self.conv2(x)))
        x = x.view(-1, 64 * 7 * 7)
        x = self.relu(self.fc1(x))
        x = self.fc2(x)
        return x

def train_mnist_demo():
    """Demo training with synthetic data (no download required)"""

    # Detect device
    if torch.cuda.is_available():
        device = "cuda"
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        device = "mps"
    else:
        device = "cpu"

    print(f"Training on device: {device}")

    # Create synthetic MNIST-like data (28x28 images, 10 classes)
    batch_size = 64
    num_batches = 50

    # Generate random data
    X = torch.randn(batch_size * num_batches, 1, 28, 28)
    y = torch.randint(0, 10, (batch_size * num_batches,))

    dataset = TensorDataset(X, y)
    dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

    # Initialize model
    model = SimpleCNN().to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=0.001)

    # Training loop
    num_epochs = 3
    print(f"\nTraining for {num_epochs} epochs...")

    for epoch in range(num_epochs):
        total_loss = 0.0
        correct = 0
        total = 0

        for batch_idx, (data, target) in enumerate(dataloader):
            data, target = data.to(device), target.to(device)

            optimizer.zero_grad()
            output = model(data)
            loss = criterion(output, target)
            loss.backward()
            optimizer.step()

            total_loss += loss.item()
            _, predicted = output.max(1)
            total += target.size(0)
            correct += predicted.eq(target).sum().item()

            if batch_idx % 10 == 0:
                print(f"Epoch [{epoch+1}/{num_epochs}], Batch [{batch_idx}/{len(dataloader)}], "
                      f"Loss: {loss.item():.4f}")

        avg_loss = total_loss / len(dataloader)
        accuracy = 100. * correct / total

        print(f"\nEpoch [{epoch+1}/{num_epochs}] Complete:")
        print(f"  Average Loss: {avg_loss:.4f}")
        print(f"  Accuracy: {accuracy:.2f}%\n")

    print("Training completed successfully!")
    return model

if __name__ == "__main__":
    train_mnist_demo()
