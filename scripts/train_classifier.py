import torch
import torch.nn as nn
import torch.optim as optim

from torchvision import datasets, transforms, models
from torch.utils.data import DataLoader
from torchvision.models import ResNet18_Weights
from tqdm import tqdm


transform = transforms.Compose([
  transforms.Resize(224),
  transforms.ToTensor(),
])

dataset = datasets.ImageFolder("dataset/", transform=transform)
train_loader = DataLoader(dataset, batch_size=16, shuffle=True)

model = models.resnet18(weights=ResNet18_Weights.IMAGENET1K_V1)
num_features = model.fc.in_features
model.fc = nn.Linear(num_features, len(dataset.classes))

criterion = nn.CrossEntropyLoss()
optimizer = optim.Adam(model.parameters(), lr=0.001)

epochs = 5
for epoch in range(epochs):
  total_loss = 0
  progress_bar = tqdm(train_loader, desc=f"Epoch {epoch+1}/{epochs}")
  for images, labels in progress_bar:
    outputs = model(images)
    loss = criterion(outputs, labels)
    optimizer.zero_grad()
    loss.backward()
    optimizer.step()
    total_loss += loss.item()
    progress_bar.set_postfix({"batch_loss": f"{loss.item():.4f}"})
    
  avg_loss = total_loss / len(train_loader)
  print(f"Epoch {epoch+1}/{epochs} completed, Average Loss: {avg_loss:.4f}")
  
torch.save(model.state_dict(), "models/animal_classifier.pth")
print("Model has been saved.")