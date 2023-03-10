# StationAssetsReport

Utilities for managing characters in Eve Online.

Asset Reporter -- generate a list of items in stations and on ships, compute a value based on current market conditions.  Generate a report sorted by aggregate value (i.e. which stations have the most valuable inventory)

Money Chart -- every time Asset Reporter is run the "net worth" of the character is stored.  Money Chart will show a historical worth graph for the character, broken down by asset types (ISK, market orders, ships, etc)

Sweeper/Sweeper2 -- Best path calculators.  Computes a "round-trip" path to pick up inventory in stations and return it to a market hub.  The path is the shortest number of hops that will pick up the highest value inventory without exceeding the cargo ship capacity.
