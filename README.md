# MarketMakingMLAlgo
This is a research about using ML or RL predictions for HFT Market Making in collaboration with [Valeria Nizolya](https://github.com/leranizolia). Backtest was build on Full order log. 

Diploma and text version of our research - https://www.hse.ru/edu/vkr/465675180

Data example - https://drive.google.com/file/d/1RvHNxroaQIJk1uxC3WIynt_cbrhgXga8/view?usp=sharing

# Project structure
1) The docs contain all the necessary information about the top-level ideas embedded in the project.
   /
2) After the documentation, you can get acquainted with the laptops. LIGHT_VERSION_FOL - the Matching Engine is presented and an example of using it for a backtest and counting all statistics, it is better to start with it. It presents the idea of a backtest.  MLBacktest contains feature generation and training of basic ml algorithms. It also provides a strategy containing artificial intelligence. All other ipynbs relate to reinforcement learning, they can be viewed independently of the others. It contains RL-specific concepts and ideas

That should be enough. It loads data from OrderLog20151010, you need to unpack the archive and you can run ipynb. In this folder there are examples of TradeLog and Order Log for this day. There are still a lot of calculated icebergs in it, these are  unnecessary technical files.
   
3) The backtest_py folder contains the classes used for the backtest. They are called in ipynb, hey can be used as black boxes. An example of use is in MLBacktest, where it is used to simulate trading days using a strategy.
