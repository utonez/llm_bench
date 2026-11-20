"""FirestoreResultRepository against an in-memory fake of the Firestore client API."""

from datetime import timedelta

from app.storage.firestore import MAX_BATCH_WRITES, FirestoreResultRepository
from tests.conftest import FIXED_NOW
from tests.test_stats import make_result


class FakeDoc:
    def __init__(self, data):
        self._data = data

    def to_dict(self):
        return dict(self._data)


class FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def where(self, *, filter):  # noqa: A002 - mirrors the Firestore API
        assert filter.op_string == ">="
        return FakeQuery([r for r in self._rows if r[filter.field_path] >= filter.value])

    def order_by(self, field, direction):
        reverse = direction == "DESCENDING"
        return FakeQuery(sorted(self._rows, key=lambda r: r[field], reverse=reverse))

    def limit(self, n):
        return FakeQuery(self._rows[:n])

    def stream(self):
        return [FakeDoc(r) for r in self._rows]


class FakeCollection(FakeQuery):
    def __init__(self, store, name):
        super().__init__(list(store.get(name, {}).values()))
        self.name = name

    def document(self, doc_id):
        return (self.name, doc_id)


class FakeBatch:
    def __init__(self, client):
        self._client = client
        self._writes = []

    def set(self, ref, data):
        self._writes.append((ref, data))

    def commit(self):
        assert len(self._writes) <= MAX_BATCH_WRITES
        self._client.commits.append(len(self._writes))
        for (collection, doc_id), data in self._writes:
            self._client.store.setdefault(collection, {})[doc_id] = data


class FakeClient:
    def __init__(self):
        self.store = {}
        self.commits = []

    def collection(self, name):
        return FakeCollection(self.store, name)

    def batch(self):
        return FakeBatch(self)


def test_saved_results_round_trip_newest_first():
    client = FakeClient()
    repo = FirestoreResultRepository(client)
    old = make_result(model="old").model_copy(update={"timestamp": FIXED_NOW - timedelta(hours=1)})
    new = make_result(model="new")

    repo.save_results([old, new])

    assert repo.list_results() == [new, old]


def test_list_filters_by_since_and_limit():
    client = FakeClient()
    repo = FirestoreResultRepository(client)
    repo.save_results(
        [
            make_result(model=str(i)).model_copy(
                update={"timestamp": FIXED_NOW + timedelta(minutes=i), "task_id": f"t{i}"}
            )
            for i in range(5)
        ]
    )

    recent = repo.list_results(since=FIXED_NOW + timedelta(minutes=2), limit=2)

    assert [r.model for r in recent] == ["4", "3"]


def test_stores_plain_values_firestore_can_index():
    client = FakeClient()
    FirestoreResultRepository(client, collection="results").save_results([make_result()])

    [stored] = client.store["results"].values()

    assert stored["category"] == "classification"
    assert type(stored["category"]) is str
    assert stored["timestamp"] == FIXED_NOW


def test_large_saves_are_split_into_batches():
    client = FakeClient()
    results = [make_result().model_copy(update={"task_id": f"t{i}"}) for i in range(1201)]

    FirestoreResultRepository(client).save_results(results)

    assert client.commits == [MAX_BATCH_WRITES, MAX_BATCH_WRITES, 201]


def test_saving_the_same_result_twice_does_not_duplicate_it():
    client = FakeClient()
    repo = FirestoreResultRepository(client)

    repo.save_results([make_result()])
    repo.save_results([make_result()])

    assert len(repo.list_results()) == 1


def test_document_ids_are_safe_for_model_names_with_slashes():
    client = FakeClient()

    FirestoreResultRepository(client).save_results([make_result(model="openai/gpt-oss-20b")])

    [doc_id] = client.store["bench_results"]
    assert "/" not in doc_id


def test_saving_nothing_makes_no_commit():
    client = FakeClient()

    FirestoreResultRepository(client).save_results([])

    assert client.commits == []
