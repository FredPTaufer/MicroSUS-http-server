"""main.py - ponto de entrada do MicroSUS.

Uso:  python main.py            (porta 8080)
      python main.py 9000       (porta 9000)
"""
import sys

from server import iniciar_servidor

if __name__ == "__main__":
    if len(sys.argv) > 1:
        iniciar_servidor(porta=int(sys.argv[1]))
    else:
        iniciar_servidor()
