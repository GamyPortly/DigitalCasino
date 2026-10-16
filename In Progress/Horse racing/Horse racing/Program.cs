namespace Horse_racing
{
    using System;
    using System.Threading;

    internal class Program
    {
        static void Main(string[] args)
        {
            // Setup initial game state
            string[] horses = { "Thunderbolt", "Shadowfax", "Blaze", "Spirit", "Comet" };
            int balance = 100;
            Random rand = new Random();
            int trackLength = 40;

            Console.WriteLine("========================================");
            Console.WriteLine("    WELCOME TO THE C# HORSE DERBY!    ");
            Console.WriteLine("========================================");

            while (balance > 0)
            {
                Console.WriteLine($"\nYour Current Balance: ${balance}");
                Console.WriteLine("Available Horses:");
                for (int i = 0; i < horses.Length; i++)
                {
                    Console.WriteLine($"{i + 1}. {horses[i]}");
                }

                // 1. Get Horse Selection
                int chosenHorseIndex = -1;
                while (chosenHorseIndex < 0 || chosenHorseIndex >= horses.Length)
                {
                    Console.Write($"\nChoose a horse to bet on (1-{horses.Length}): ");
                    if (int.TryParse(Console.ReadLine(), out int choice) && choice >= 1 && choice <= horses.Length)
                    {
                        chosenHorseIndex = choice - 1;
                    }
                    else
                    {
                        Console.WriteLine("Invalid selection. Please pick a number from the list.");
                    }
                }

                // 2. Get Bet Amount
                int betAmount = 0;
                while (betAmount <= 0 || betAmount > balance)
                {
                    Console.Write($"Enter your bet amount (Max ${balance}): $");
                    if (!int.TryParse(Console.ReadLine(), out betAmount) || betAmount <= 0 || betAmount > balance)
                    {
                        Console.WriteLine("Invalid bet amount. You cannot bet more than your balance.");
                        betAmount = 0;
                    }
                }

                balance -= betAmount;
                Console.Clear();
                Console.WriteLine("GET READY TO RACE...");
                Thread.Sleep(1500);

                // 3. Race Setup
                int[] positions = new int[horses.Length];
                bool raceFinished = false;
                int winningHorseIndex = -1;

                // 4. Main Race Animation Loop
                while (!raceFinished)
                {
                    Console.Clear();
                    Console.WriteLine("--- THE RACE IS UNDERWAY ---");
                    Console.WriteLine(new string('=', trackLength + 10));

                    for (int i = 0; i < horses.Length; i++)
                    {
                        // Advance horse by a random step (0 to 3 units)
                        positions[i] += rand.Next(0, 4);

                        // Cap position at finish line
                        if (positions[i] >= trackLength)
                        {
                            positions[i] = trackLength;
                            if (!raceFinished)
                            {
                                raceFinished = true;
                                winningHorseIndex = i; // First horse to cross wins
                            }
                        }

                        // Render the track line for the horse
                        string lane = new string('.', positions[i]) + "🐎" + new string(' ', trackLength - positions[i]);
                        Console.WriteLine($"{horses[i].PadRight(12)} |{lane}| Finish");
                    }

                    Console.WriteLine(new string('=', trackLength + 10));
                    Thread.Sleep(200); // Controlling animation speed (200ms ticks)
                }

                // 5. Process Betting Payouts
                Console.WriteLine($"\n🏁 WINNER: {horses[winningHorseIndex]}! 🏁");
                if (winningHorseIndex == chosenHorseIndex)
                {
                    int winnings = betAmount * 4; // 4x payout multiplier
                    balance += winnings;
                    Console.ForegroundColor = ConsoleColor.Green;
                    Console.WriteLine($"🎉 Congratulations! You won ${winnings}!");
                    Console.ResetColor();
                }
                else
                {
                    Console.ForegroundColor = ConsoleColor.Red;
                    Console.WriteLine($"❌ {horses[chosenHorseIndex]} lost. You lost your bet of ${betAmount}.");
                    Console.ResetColor();
                }

                if (balance <= 0)
                {
                    Console.WriteLine("\n💀 You are bankrupt! Game over.");
                    break;
                }

                // 6. Play Again Prompt
                Console.Write("\nDo you want to race again? (y/n): ");
                string response = Console.ReadLine()?.ToLower();
                if (response != "y" && response != "yes")
                {
                    break;
                }
            }

            Console.WriteLine($"\nThanks for playing! You walked away with ${balance}.");
        }
    }

}
