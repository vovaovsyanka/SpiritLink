"""Двунаправленная LSTM поверх замороженных эмбеддингов."""

import torch
import torch.nn as nn

from app import settings
from app.text_utils import tokenize

from .base import DEVICE, BaseClassifier


class MyLSTM(nn.Module):
    def __init__(self, vocab_size, embedding_dim, hidden_dim, num_classes, embedding_matrix):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, embedding_dim)
        self.embedding.weight = nn.Parameter(torch.FloatTensor(embedding_matrix))
        self.embedding.weight.requires_grad = False

        self.lstm1 = nn.LSTM(embedding_dim, hidden_dim, batch_first=True, bidirectional=True, dropout=0.2)
        self.lstm2 = nn.LSTM(hidden_dim * 2, hidden_dim // 2, batch_first=True, bidirectional=True, dropout=0.2)

        self.fc1 = nn.Linear(hidden_dim, 64)
        self.dropout1 = nn.Dropout(0.5)
        self.fc2 = nn.Linear(64, 32)
        self.dropout2 = nn.Dropout(0.3)
        self.fc3 = nn.Linear(32, num_classes)
        self.relu = nn.ReLU()

    def forward(self, x):
        lstm_out1, _ = self.lstm1(self.embedding(x))
        _, (hidden2, _) = self.lstm2(lstm_out1)
        features = torch.cat((hidden2[-2], hidden2[-1]), dim=1)

        x = self.dropout1(self.relu(self.fc1(features)))
        x = self.dropout2(self.relu(self.fc2(x)))
        return self.fc3(x)


class LSTM(BaseClassifier):
    name = "LSTM"

    def __init__(self):
        # weights_only=False: чекпойнт содержит label_encoder и word_index
        ckpt = torch.load(settings.LSTM_PATH, map_location=DEVICE, weights_only=False)
        self.model = MyLSTM(
            vocab_size=ckpt["vocab_size"],
            embedding_dim=ckpt["embedding_dim"],
            hidden_dim=ckpt["hidden_dim"],
            num_classes=ckpt["num_classes"],
            embedding_matrix=ckpt["embedding_matrix"],
        ).to(DEVICE)
        self.model.load_state_dict(ckpt["model_state_dict"])
        self.model.eval()

        self.word_index = ckpt["word_index"]
        self.label_encoder = ckpt["label_encoder"]
        self.max_length = ckpt["max_sequence_length"]

    def _encode(self, text: str) -> torch.Tensor:
        ids = [self.word_index.get(token, 0) for token in tokenize(text)][: self.max_length]
        ids += [0] * (self.max_length - len(ids))
        return torch.tensor(ids, dtype=torch.long).unsqueeze(0).to(DEVICE)

    def classify(self, text: str) -> int:
        with torch.no_grad():
            predicted = self.model(self._encode(text)).argmax(dim=1).cpu().numpy()
        return 1 if self.label_encoder.inverse_transform(predicted)[0] == "unsafe" else 0
