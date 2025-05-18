from models.dbmodels import Portal
from utils.cartography import translated_djikstra, best_guesses

def test_djikstra():
    print(best_guesses("tp"))
    # print(translated_djikstra("Scuttlesink Marsh", "Fort Sterling"))
    # test_queries()
    import datetime as dt
    def construct_portal(m1: str, m2: str) -> Portal:
        return Portal(
            from_map=m1, to_map=m2,
            time_expire=dt.datetime.now()+dt.timedelta(days=1), submitter="test", time_submitted=dt.datetime.now()
        )
    connections = [
        ('Scuttlesink Marsh', 'Qiient-Al-Nusom'),
        ('Qiient-Al-Nusom', 'Whitebank Descent'),
    ]
    print(translated_djikstra("Scuttlesink Marsh", "Fort Sterling", roads=[construct_portal(*c) for c in connections]))

if __name__ == "__main__":
    test_djikstra()
