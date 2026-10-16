//Table of lies, total amount of cards = 20 ( 6 kings, 6 queens, 6 jacks, 2 jokers), a specific rank (king, queen jack) is chosen and the player has to either bluff or actually play that rank, only the next person in "lin" can call them out )
int totalCards = 20;
int AmountOfKings = 6;
int AmountOfQueens = 6;
int AmountOfJacks = 6;
int AmountOfJokers = 2;

int timer = 20;
int currentPlayer = 0;
int currentRank = 0;
enum Ranks { King, Queen, Jack,};

