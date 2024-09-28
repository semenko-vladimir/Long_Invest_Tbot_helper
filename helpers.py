
def calculate_profit(average_position_price, current_price_one, brokerFee=0.3):

    comission = (average_position_price + current_price_one) * brokerFee / 100

    profit = current_price_one - average_position_price - comission

    current_profit = 100 * profit / average_position_price

    return current_profit


