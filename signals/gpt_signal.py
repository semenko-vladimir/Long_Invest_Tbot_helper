import g4f
from g4f.client import Client


def calculate_gpt_strategy(text, profit, ticker):

    response = None

    text += "\nТекущая прибыль в %: " + str(profit)
    text += "\nТикер: " + ticker


    client = Client()

    response = client.chat.completions.create(
        model=g4f.models.gpt_4o_mini,
        messages=[{"role": "user", "content": text}],
    )

    r = response.choices[0].message.content

    print(r)

    return r.lower()

