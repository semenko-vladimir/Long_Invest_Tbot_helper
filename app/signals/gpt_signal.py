import g4f
from g4f.client import Client


def calculate_gpt_strategy(text, profit, ticker):

    """
    Рассчитывает стратегию GPT на основе текста, прибыли и тикера.

    :param text: текст, на основе которого будет рассчитана стратегия
    :param profit: прибыль в %
    :param ticker: тикер
    :return: рассчитанная стратегия (str, может быть buy, sell, hold)
    """
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

