from profanity_check import predict_prob

def check_profanity(text, threshold=0.75):
    """
    Checks if the provided text contains profanity using alt-profanity-check.
    
    Args:
        text: The text to check for profanity
        threshold: The probability threshold above which the text is considered profane (default: 0.75)
        
    Returns:
        Boolean indicating whether the text contains profanity
    """
    if not text:
        return False
    
    # Get profanity probability from the model
    probability = predict_prob([text])[0]
    
    # Return True if probability is above threshold
    return probability > threshold 