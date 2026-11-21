from collections import Counter

NEIGHBORS = ((-1, 0), (1, 0), (0, -1), (0, 1))


def components(cells):
    failed = {(cell["x"], cell["y"]): cell for cell in cells.values() if cell["result"] == "FAIL"}
    visited = set()
    groups = []
    for anchor in sorted(failed, key=lambda point: (-point[1], point[0])):
        if anchor in visited:
            continue
        visited.add(anchor)
        queue = [anchor]
        points = []
        while queue:
            x, y = queue.pop()
            points.append((x, y))
            for dx, dy in NEIGHBORS:
                adjacent = (x + dx, y + dy)
                if adjacent in failed and adjacent not in visited:
                    visited.add(adjacent)
                    queue.append(adjacent)
        points.sort(key=lambda point: (-point[1], point[0]))
        bins = Counter(str(failed[point]["bin"]) for point in points)
        groups.append({"id": f"C{len(groups) + 1:02d}", "size": len(points), "anchor": anchor,
                       "bounds": [min(x for x, _ in points), min(y for _, y in points),
                                  max(x for x, _ in points), max(y for _, y in points)],
                       "bins": dict(sorted(bins.items())), "points": points,
                       "evidence": [row for point in points for row in failed[point]["evidence"]]})
    return groups
