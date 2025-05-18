from bisect import bisect_left

class SubstringSearcher:
    def __init__(self, string_list: list[str]) -> None:
        self.strings = list(string_list)
        # Build a suffix array (sorted list of all suffixes)
        self.suffixes = []
        for idx, s in enumerate(string_list):
            self.suffixes.append((s.lower(), idx))
            for word in s.replace('-', ' ').lower().split():
                for i in range(len(word)):
                    self.suffixes.append((word[i:], idx))
        self.suffixes.sort()
    
    def get(self, query: str) -> list[str]:
        query = query.lower()
        # Binary search to find the first matching suffix
        left = bisect_left(self.suffixes, (query, 0))
        results = set()
        # Collect all strings that have this prefix in their suffix
        for i in range(left, len(self.suffixes)):
            if not self.suffixes[i][0].startswith(query):
                break
            results.add(self.strings[self.suffixes[i][1]])
        return list(results)