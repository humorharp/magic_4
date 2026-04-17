from num2words import num2words
from word2number import w2n

def count_letters(word: str) -> int:
    """Count the number of letters in a word, ignoring spaces and hyphens."""
    return len(word.replace(" ", "").replace("-", ""))

# Ask the user for a number or word
user_input = input("Enter a number (like 5 or 'five'): ").strip()

# Try to convert to number
try:
    if user_input.isdigit() or (user_input.startswith('-') and user_input[1:].isdigit()):
        user_number = int(user_input)
    else:
        user_number = w2n.word_to_num(user_input)
except ValueError:
    print("Sorry, I don't recognize that as a number!")
    exit()

# Build the chain
chain_parts = []
current_number = user_number

while True:
    word_form = num2words(current_number)
    letter_count = count_letters(word_form)
    
    if letter_count == 4:
        chain_parts.append(f"{current_number} is {letter_count}")
        break
    else:
        chain_parts.append(f"{current_number} is {letter_count}")
        current_number = letter_count

# Create the narrative
narrative = ", then ".join(chain_parts) + ", and 4 is the magic number!"
print(narrative)