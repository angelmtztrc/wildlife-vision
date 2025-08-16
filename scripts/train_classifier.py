import torch
from torchvision import datasets, transforms, models
from torch.utils.data import DataLoader
import torch.nn as nn
import torch.optim as optim

transform = transforms.Compose([
  transforms.Resize(224),
  transforms.ToTensor(),
])

dataset = datasets.ImageFolder("dataset/", transform=transform)
train_loader = DataLoader(dataset, batch_size=16, shuffle=True)

model = models.resnet18(pretrained=True)
num_features = model.fc.in_features
model.fc = nn.Linear(num_features, len(dataset.classes))

criterion = nn.CrossEntropyLoss()
optimizer = optim.Adam(model.parameters(), lr=0.001)

epochs = 5
for epoch in range(epochs):
  total_loss = 0
  for images, labels in train_loader:
    outputs = model(images)
    loss = criterion(outputs, labels)
    optimizer.zero_grad()
    loss.backward()
    optimizer.step()
    total_loss += loss.item()
  print(f"Epoch {epoch+1}/{epochs}, Loss: {total_loss/len(train_loader)}")
  
torch.save(model.state_dict(), "models/animal_classifier.pth")
print("Model has been saved.")