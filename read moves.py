import chess
board = chess.Board()
print("All legal moves for White:")
for move in board.legal_moves:
    print(move)

board.push_san("e2e4")

print("\nBoard after White moves pawn to e4:")
print(board)