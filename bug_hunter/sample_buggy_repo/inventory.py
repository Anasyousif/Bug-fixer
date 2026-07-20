"""A small (intentionally buggy) inventory management module used to
demo Bug Hunter. Every function below has at least one real bug."""


class Warehouse:
    # BUG: mutable class attribute shared across every Warehouse instance
    pending_orders = []

    def __init__(self, name):
        self.name = name

    def queue_order(self, order):
        self.pending_orders.append(order)


def add_item(item, bucket=[]):
    # BUG: mutable default argument — bucket persists across calls
    bucket.append(item)
    return bucket


def load_config(path):
    # BUG: file opened without a context manager
    f = open(path)
    data = f.read()
    return data


def get_price(item):
    if item.price == None:
        return 0
    return item.price


def process_order(order):
    try:
        validate(order)
    except ValueError as e:
        log_error(e)
        raise e  # BUG: resets traceback


def remove_out_of_stock(items):
    for item in items:
        if item.stock == 0:
            items.remove(item)  # BUG: mutating list while iterating


def fetch_remote_data(url):
    try:
        return call_api(url)
    except:  # BUG: bare except
        return None


def validate(order):
    if order is None:
        raise ValueError("order cannot be None")


def log_error(e):
    print(f"error: {e}")


def call_api(url):
    return {"status": "ok"}
