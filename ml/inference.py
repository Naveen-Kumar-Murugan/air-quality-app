"""SageMaker PyTorch inference handlers for the six ordered AQI classes."""

import io
import json
import os

CLASS_NAMES = [
    "Good",
    "Moderate",
    "Unhealthy for Sensitive Groups",
    "Unhealthy",
    "Very Unhealthy",
    "Hazardous",
]


def model_fn(model_dir):
    import torch
    from torchvision.models import mobilenet_v2

    artifact_path = os.path.join(model_dir, "model.pt")
    checkpoint = torch.load(artifact_path, map_location="cpu", weights_only=True)
    model = mobilenet_v2(weights=None)
    model.classifier[1] = torch.nn.Linear(model.last_channel, len(CLASS_NAMES))
    model.load_state_dict(checkpoint["state_dict"] if "state_dict" in checkpoint else checkpoint)
    model.eval()
    return model


def input_fn(request_body, content_type):
    if content_type not in ("image/jpeg", "image/jpg", "application/octet-stream"):
        raise ValueError(f"Unsupported content type: {content_type}")

    from PIL import Image, UnidentifiedImageError
    from torchvision import transforms

    try:
        image = Image.open(io.BytesIO(request_body)).convert("RGB")
    except (UnidentifiedImageError, OSError) as error:
        raise ValueError("Request body must contain a valid JPEG image") from error

    transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
    ])
    return transform(image).unsqueeze(0)


def predict_fn(input_data, model):
    import torch

    with torch.inference_mode():
        probabilities = torch.softmax(model(input_data), dim=1)[0].cpu().tolist()
    index = max(range(len(probabilities)), key=probabilities.__getitem__)
    return {"probs": probabilities, "label": CLASS_NAMES[index]}


def output_fn(prediction, accept):
    if accept not in ("application/json", "*/*"):
        raise ValueError(f"Unsupported accept type: {accept}")
    return json.dumps(prediction), "application/json"
