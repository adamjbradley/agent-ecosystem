def compute_trust(feedback_list):
    return sum(feedback_list)/len(feedback_list) if feedback_list else 0
