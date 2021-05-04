import math


def get_within_threshold(cx, cy, others, threshold):

    result = {}

    for o in others:
        other = others[o]

        ox = other['x']
        oy = other['y']

        sqr_dist = compute_sqr_distance(cx, cy, ox, oy)
        if sqr_dist <= threshold * threshold:
            result[o] = math.sqrt(sqr_dist)

    return result


def compute_sqr_distance(x0, y0, x1, y1):
    return (x1 - x0)**2 + (y1 - y0)**2