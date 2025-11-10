from multiprocessing import set_start_method

is_initialized = False


def set_start_method_fork():
    global is_initialized

    if not is_initialized:
        set_start_method("fork", True)
        is_initialized = True
