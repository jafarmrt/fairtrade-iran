"""
Cart, checkout and orders of the shop.

A cart may hold products of several producers. At checkout it becomes one
Purchase (what the buyer sees, with one code) split into one Order per
producer, because each producer ships separately and may be paid in a
different way:

    house     the buyer pays the House (online or bank transfer + receipt);
              the House confirms, keeps its commission and pays the producer.
    producer  the buyer pays the producer directly (to the producer's card);
              the producer confirms in the member panel and owes the House
              its commission.

Producers whose seller mode is "none" keep only the "direct purchase" link.
"""
