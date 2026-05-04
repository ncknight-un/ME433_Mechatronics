import pgzrun

# Size of the window
WIDTH = 800
HEIGHT = 800

# Starting position
x = 0
y = 0

def update():
    global x
    global y
    x = x + 1
    y = y + 1

    if x > 750:
        x = 0
    if y > 500:
        y = 0


def draw():
    screen.clear()
    screen.draw.circle((x, y), 20, "white")

pgzrun.go()