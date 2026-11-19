"""Testaufbau außerhalb des Produktcodes."""
from stadtmeisterschaft.domain import FightResult
from stadtmeisterschaft.storage import Store
from stadtmeisterschaft.ui.main_window import Window

from .demo_data import demo


def demo_window(folder, count=10):
    folder.mkdir(parents=True, exist_ok=True)
    store = Store(folder)
    if store.load() is None:
        store.save(demo(count))
    return Window(folder)


def record_result(state, pool_id, winner, first, second):
    outcome = {"Erstes Kind": "1:0", "Zweites Kind": "0:1", "Unentschieden": "0:0"}[winner]
    pool = state.pool(pool_id)
    state.save_pool(pool_id, pool.name, pool.results | {"1": FightResult(outcome, first, second)})
