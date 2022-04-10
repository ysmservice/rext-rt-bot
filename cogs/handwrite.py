from discord.ext import commands
from keras.datasets import mnist
import discord
import keras

from rtlib import Cog, Embed

class HandWrite(Cog):
    def __init__(self, bot):
        self.bot = bot
        self.model = keras.models.load_model("data/models/handwrite_model.h5")
        self.test()
        
    def test(self):
        (x_train, y_train), (x_test, y_test) = mnist.load_data()
        x_train, x_test = x_train / 255.0, x_test / 255.0
        print(self..evaluate(x_test,  y_test, verbose=2))
        
async def setup(bot):
    await bot.add_cog(HandWrite(bot))
