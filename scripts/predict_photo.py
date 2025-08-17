import os
import torch

from torchvision import transforms, models
from PIL import Image
from utils.prompt import prompt_path

# Define same transforms used for training
transform = transforms.Compose([
    transforms.Resize(224),
    transforms.ToTensor(),
])

# The class names should match dataset subfolders
classes = ["animal", "empty", "object"]

# Load model
model = models.resnet18(weights=None)
num_features = model.fc.in_features
model.fc = torch.nn.Linear(num_features, len(classes))
model.load_state_dict(torch.load("models/animal_classifier.pth", map_location="cpu"))
model.eval()

def predict(img_path):
  image = Image.open(img_path).convert("RGB")
  input_tensor = transform(image).unsqueeze(0)
  
  with torch.no_grad():
    output = model(input_tensor)
    probabilities = torch.nn.functional.softmax(output, dim=1)
    confidence, predicted = torch.max(probabilities, 1)
    
    predicted_class = classes[predicted.item()]
    confidence_percent = confidence.item() * 100
    return predicted_class, confidence_percent

if __name__ == "__main__":
  input_path = prompt_path("Enter the path of the photo: ").strip()
  if not os.path.exists(input_path):
    print(f"Input path does not exist: {input_path}")
    exit(1)
  
  prediction, confidence = predict(input_path)
  print(f"Prediction: {prediction} ({confidence:.2f}%)")