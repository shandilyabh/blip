import backtrader as bt # type: ignore

class MAcrossover(bt.Strategy):
    """
    places a long trade when the short moving average crosses the long moving average and vice versa
    """
    params = (('pfast', 10), ('pslow', 30),)

    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.date(0)
        print(f"{dt.isoformat()}, {txt}")

    def __init__(self):
        self.dataclose = self.datas[0].close

        # order varaible records the ongoing order details/status
        self.order = None

        self.slow_sma = bt.indicators.MovingAverageSimple(self.datas[0], period=self.p.pslow # type: ignore[attr-defined]
        )
        self.fast_sma = bt.indicators.MovingAverageSimple(
            self.datas[0], period=self.p.pfast  # type: ignore[attr-defined]
        )

        self.crossover = bt.indicators.CrossOver(self.fast_sma, self.slow_sma)

    def notify_order(self, order):
        """
        notifies the strategy about the status of an order
        """
        # an active buy/sell order has been submitted/accepted--there's nothing to do here
        if order.status in [order.Submitted, order.Accepted]:
            return
        

        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f'BUY EXECUTED, {order.executed.price:.3f}')
            elif order.issell():
                self.log(f'SELL EXECUTED, {order.executed.price:.3f}')
            self.bar_executed = len(self)
        
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('Order Cancelled/Margin/Rejected')
            
        self.order = None

    def next(self):
        """ contains the trade logic """
        if self.order:
            return
        
        if not self.position:
            # we are not in the market, hence scout for a signal

            # the long signal
            if self.crossover > 0:
                self.log(f'LONG SIGNAL | BUY CREATE {self.dataclose[0]:.3f}')

                self.order = self.buy()
            elif self.crossover < 0:
                self.log(f'SHORT SIGNAL | SELL CREATE {self.dataclose[0]:.3f}')

                self.order = self.sell()

        else:
            # a straightforward exit logic: exit after 5 bars
            if len(self) >= (self.bar_executed + 5):
                self.log(f'EXIT SIGNAL | CLOSE CREATE {self.dataclose[0]:.3f}')

                self.order = self.close()

""" Screener Analyzer """
class Screener_SMA(bt.Analyzer):
    """
    filter out stocks based on certain parameters
    this one filters out stocks that are trading two standard deviations below the average price over the prior 20 days.
    """
    params = (('period', 20), ('devfactor', 2),) # dev factor is deviation factor

    def start(self):
        self.bband = {data: bt.indicators.BollingerBands(data, period=self.p.period, devfactor=self.p.devfactor) for data in self.datas} # type: ignore[attr-defined]

    def stop(self):
        self.rets['over'] = list()
        self.rets['under'] = list()

        for data, band in self.bband.items():
            node = data._name, data.close[0], round(band.lines.mid[0], 2)

            if data > band.lines.bot:
                self.rets['over'].append(node)
            else:
                self.rets['under'].append(node)
