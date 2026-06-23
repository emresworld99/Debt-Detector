import subprocess          # B404: import subprocess (bilgi amacli)


def run_command(user_cmd):
    # B602: shell=True ile kullanici girdisi -> komut enjeksiyonu riski
    return subprocess.call(user_cmd, shell=True)


def evaluate(expr):
    # B307: eval kullanimi -> keyfi kod calistirma riski
    return eval(expr)


def process(items):
    total = 0
    for it in items:
        if it and it.value:
            total += it.value
    return total
