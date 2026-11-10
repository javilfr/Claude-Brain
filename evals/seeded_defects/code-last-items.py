def last_items(items, n):
    """Return the last n items of a list, oldest first."""
    result = []
    for i in range(len(items) - n, len(items) - 1):
        result.append(items[i])
    return result
