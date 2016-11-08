from model.ActionType import ActionType
from model.Game import Game
from model.Move import Move
from model.Wizard import Wizard
from model.World import World
from model.LaneType import LaneType
from random import randrange


class MyStrategy:

    def __init__(self):
        self.lane = None
        self.lane_point_index = 0
        self.lane_BOTTOM = []
        self.lane_MIDDLE = []
        self.lane_TOP = []
        self.step_coordinates = None

    def move(self, me: Wizard, world: World, game: Game, move: Move):
        if world.tick_index == 1:
            self.init()
            return

        move.speed = game.wizard_forward_speed
        move.strafe_speed = game.wizard_strafe_speed
        move.turn = game.wizard_max_turn_angle
        move.action = ActionType.MAGIC_MISSILE

    def init(self):
        self.lane = randrange(LaneType.BOTTOM, LaneType.MIDDLE, LaneType.TOP)
        self.lane_BOTTOM = [[0, 800],
                            [500, 800],
                            [1000, 800],
                            [1500, 800],
                            [2000, 800],
                            [2500, 800],
                            [3000, 800],
                            [3500, 800]]

    def map_master(self, lane, lane_point_index, direction):

        if direction == 1:
            pass
        else:
            pass
