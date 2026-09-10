import numpy as np

def transcribe(speech_recognition_model, audio):
    if audio is None:
        print("Звук не був записаний.")
        return []
    
    if isinstance(audio, np.ndarray) and len(audio) == 0:
        print("Звук не був записаний.")
        return []
    
    segments, info = speech_recognition_model.transcribe(
        audio,
        language="uk",
        beam_size=3,
        temperature=0.0,
        vad_filter=True,
        condition_on_previous_text=True,
        word_timestamps=True,
    )
    
    words = []
    
    for segment in segments:
        if segment.words is None:
            continue
    
        for word in segment.words:
            text = word.word.strip()
    
            if text:
                words.append(text)
    
    return words
