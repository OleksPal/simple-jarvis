from sentence_transformers import SentenceTransformer, util
from torch import Tensor

from src.command_manager import get_command_name

def find_best_command_match(
    model: SentenceTransformer,
    encoded_options: Tensor,
    phrase: str
) -> tuple[str, float]:
    phrase_vector = model.encode(phrase, convert_to_tensor=True)

    scores = util.cos_sim(phrase_vector, encoded_options)[0]
    best_index = scores.argmax().item()

    return best_index, scores[best_index].item()

def get_command(
    resolver_model: SentenceTransformer,
    encoded_options: Tensor,
    options: list[str],
    phrase: str,
    commands,
    threshold=0.8
) -> str:
    option_index, score = find_best_command_match(resolver_model, encoded_options, phrase)

    if score >= threshold:        
        phrase = options[option_index]
        return get_command_name(phrase, commands)
    else:
        return None

def encode_options(
    model: SentenceTransformer,
    options: list[str]
) -> Tensor:
    return model.encode(options, convert_to_tensor=True)
