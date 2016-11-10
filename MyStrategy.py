from model.Game import Game
from model.Move import Move
from model.Wizard import Wizard
from model.World import World
from model.LaneType import LaneType
from model.ActionType import ActionType
from model.Faction import Faction
from random import randrange, uniform
from math import sin, fabs
import copy
from time import time

try:
    from debug_client import DebugClient
    from debug_client import Color
except:
    debug = None
else:
    debug = DebugClient()


def clamp(n, smallest, largest):
        return max(smallest, min(n, largest))


class MyStrategy:

    def __init__(self):
        # ------------------------------
        self.area = [] # debug
        self.width = None
        self.x_cage_offset = None
        self.y_cage_offset = None
        # ------------------------------
        self.lane = None
        self.x, self.y = None, None
        self.lane_point_index = 0
        self.lane_array_BOTTOM = []
        self.lane_array_MIDDLE = []
        self.lane_array_TOP = []
        self.target_point_x, self.target_point_y = None, None
        self.step_point_x, self.step_point_y = None, None
        self.last5step = [[1, 2], [3, 4], [5, 6], [7, 8], [9, 10]]
        self.is_stuck = False
        self.stuck_start_tick = None
        self.status = "go"   # "go", "fight", "stuck"
        self.faction = None
        self.enemy_faction = None
        self.lane_array_BOTTOM = [[250, 3800],
                                  [600, 3800],
                                  [1000, 3800],
                                  [1400, 3800],
                                  [1800, 3800],
                                  [2200, 3800],
                                  [2600, 3800],
                                  [3000, 3800],
                                  [3400, 3800],
                                  [3600, 3700],
                                  [3800, 3600],
                                  [3850, 3300],
                                  [3850, 3000],
                                  [3850, 2600],
                                  [3850, 2200],
                                  [3850, 1800],
                                  [3850, 1400],
                                  [3850, 1000],
                                  [3850, 600],
                                  [3850, 200],]

    def move(self, me: Wizard, world: World, game: Game, move: Move):
        if world.tick_index == 0:
            self.init(me)
            return
        #c = time()
        self.x = me.x
        self.y = me.y

        if me.life < me.max_life * 0.3:
            self.map_master(-1)
        elif me.get_distance_to(self.target_point_x, self.target_point_y) < 200:
            self.map_master(1)

        self.step_point_x, self.step_point_y = self.find_way(world, me)
        self.stuck_check()
        self.attack(move, game, me, self.situation_analysis(world, me, move))
        self.go(me, move, game, world.tick_index)
        self.debug_func(world)

    def attack(self, move, game, me, enemy):
        if enemy is None:
            return
        angle = me.get_angle_to(enemy.x, enemy.y)
        move.turn = angle
        if fabs(angle) < game.staff_sector / 2:
            move.cast_angle = angle
            move.min_cast_distance = me.get_distance_to(enemy.x, enemy.y) #- enemy.radius + game.getMagicMissileRadius
            move.action = ActionType.MAGIC_MISSILE

    def situation_analysis(self, world, me, move):
        minions, wizards = [], []
        for i in world.wizards:
            if i.faction == self.enemy_faction:
                if me.get_distance_to(i.x, i.y) < me.cast_range:
                    wizards.append(i)
        if len(wizards) > 0:
            wizards.sort(key=lambda x: x.life)
            self.status = "fight"
            return wizards[0]
        for i in world.minions:
            if i.faction == self.enemy_faction:
                if me.get_distance_to(i.x, i.y) < me.cast_range:
                    minions.append(i)
        if len(minions) > 0:
            minions.sort(key=lambda x: x.life)
            self.status = "fight"
            return minions[0]
        return None

    def init(self, me):
        # self.lane = randrange(LaneType.BOTTOM, LaneType.MIDDLE, LaneType.TOP)
        self.lane = LaneType.BOTTOM
        self.x = me.x
        self.y = me.y
        self.target_point_x, self.target_point_y = self.x, self.y
        self.faction = me.faction
        if self.faction == Faction.ACADEMY:
            self.enemy_faction = Faction.RENEGADES
        else:
            self.enemy_faction = Faction.ACADEMY

    def map_master(self, direction):
        lane_array = None

        if self.lane == LaneType.BOTTOM:
            lane_array = self.lane_array_BOTTOM
        elif self.lane == LaneType.MIDDLE:
            lane_array = self.lane_array_MIDDLE
        elif self.lane == LaneType.TOP:
            lane_array = self.lane_array_TOP

        lane_array_len = len(lane_array)
        if direction == 1:
            if self.lane_point_index != lane_array_len - 1:
                self.lane_point_index += 1
        else:
            if self.lane_point_index != 0:
                self.lane_point_index -= 1
        self.target_point_x, self.target_point_y = lane_array[self.lane_point_index]

    def stuck_check(self):
        if self.status == "stuck":
            return
        for i in range(4):
            self.last5step[i][0] = self.last5step[i + 1][0]
            self.last5step[i][1] = self.last5step[i + 1][1]
        self.last5step[4] = [self.x, self.y]
        for i in range(3):
            if self.last5step[i] != self.last5step[i + 1]:
                self.is_stuck = False
                break
        else:
            self.is_stuck = True
            self.status = "stuck"

    def go(self, me, move, game, tick):
        if self.status == "go":
            move.turn = clamp(me.get_angle_to(self.step_point_x, self.step_point_y),
                              -game.wizard_max_turn_angle, game.wizard_max_turn_angle)
            move.speed = game.wizard_forward_speed * (1 - 0.5 * move.turn / game.wizard_max_turn_angle)
            #move.strafe_speed += game.wizard_strafe_speed * sin(0.05 * tick) * 0.2
        elif self.status == "fight":
            pass
        elif self.status == "stuck":
            if self.stuck_start_tick is None:
                self.stuck_start_tick = tick
            elif tick - self.stuck_start_tick > 20:
                self.status = "go"
                self.stuck_start_tick = None
            move.speed = -game.wizard_forward_speed
            move.turn = uniform(-game.wizard_max_turn_angle, game.wizard_max_turn_angle)

    def find_way(self, world, me):
        width = 50
        k = int(800 / width - 1)
        if self.x > 400:
            x_cage_offset = int((self.x - 400) // width)
        else:
            x_cage_offset = int((self.x - 400) // width) + 1
        if self.y > 400:
            y_cage_offset = int((self.y - 400) // width)
        else:
            y_cage_offset = int((self.y - 400) // width) + 1
        stop_x = int(clamp(self.target_point_x // width - x_cage_offset, 0, k))
        stop_y = int(clamp(self.target_point_y // width - y_cage_offset, 0, k))
        area = [[0 for i in range(int(800 / width))] for j in range(int(800 / width))]
        for i in world.buildings:
            if me.get_distance_to(i.x, i.y) < 400 - width:
                area[int(i.x // width - x_cage_offset)][int(i.y // width - y_cage_offset)] = 1
        for i in world.minions:
            if me.get_distance_to(i.x, i.y) < 400 - width:
                area[int(i.x // width - x_cage_offset)][int(i.y // width - y_cage_offset)] = 1
        for i in world.wizards:
            if me.get_distance_to(i.x, i.y) < 400 - width:
                area[int(i.x // width - x_cage_offset)][int(i.y // width - y_cage_offset)] = 1
        for i in world.trees:
            if me.get_distance_to(i.x, i.y) < 400 - width:
                area[int(i.x // width - x_cage_offset)][int(i.y // width - y_cage_offset)] = 1
        area[int(self.x // width - x_cage_offset)][int(self.y // width - y_cage_offset)] = 0
        # ------------------------------------
        self.area = copy.deepcopy(area) # debug
        self.width = width # debug
        self.x_cage_offset = x_cage_offset
        self.y_cage_offset = y_cage_offset
        # ------------------------------------
        points = [[int(self.x // width - x_cage_offset), int(self.y // width - y_cage_offset)]] # Start points... ???
        index = 1
        break_flag = True
        # bfs
        while break_flag and len(points) != 0:
            index += 1
            add_to_points = []
            for i in points:
                x, y = i[0], i[1]
                if x == stop_x and y == stop_y:
                    break_flag = False
                    break
                area[x][y] = index - 1
                if x != k:
                    if area[x+1][y] == 0:
                        area[x+1][y] = index
                        add_to_points.append([x+1, y])
                    if y != k:
                        if area[x+1][y+1] == 0:
                            area[x+1][y+1] = index
                            add_to_points.append([x+1, y+1])
                    if y != 0:
                        if area[x+1][y-1] == 0:
                            area[x+1][y-1] = index
                            add_to_points.append([x+1, y-1])
                if x != 0:
                    if area[x-1][y] == 0:
                        area[x-1][y] = index
                        add_to_points.append([x-1, y])
                    if y != k:
                        if area[x-1][y+1] == 0:
                            area[x-1][y+1] = index
                            add_to_points.append([x-1, y+1])
                    if y != 0:
                        if area[x-1][y-1] == 0:
                            area[x-1][y-1] = index
                            add_to_points.append([x-1, y-1])
                if y != k:
                    if area[x][y+1] == 0:
                        area[x][y+1] = index
                        add_to_points.append([x, y+1])
                if y != 0:
                    if area[x][y-1] == 0:
                        area[x][y-1] = index
                        add_to_points.append([x, y-1])
            points = add_to_points

        # find way in array
        way = []
        index = area[stop_x][stop_y]
        x, y = stop_x, stop_y
        if index > 1:
            while index != 2:
                index -= 1
                if x != k:
                    if area[x + 1][y] == index:
                        x, y = x + 1, y
                        continue
                    if y != k:
                        if area[x + 1][y + 1] == index:
                            x, y = x + 1, y + 1
                            continue
                    if y != 0:
                        if area[x + 1][y - 1] == index:
                            x, y = x + 1, y - 1
                            continue
                if x != 0:
                    if area[x - 1][y] == index:
                        x, y = x - 1, y
                        continue
                    if y != k:
                        if area[x - 1][y + 1] == index:
                            x, y = x - 1, y + 1
                            continue
                    if y != 0:
                        if area[x - 1][y - 1] == index:
                            x, y = x - 1, y - 1
                            continue
                if y != k:
                    if area[x][y + 1] == index:
                        x, y = x, y + 1
                        continue
                if y != 0:
                    if area[x][y - 1] == 0:
                        x, y = x, y - 1
                        continue

        return (x + x_cage_offset) * width + width / 2, (y + y_cage_offset) * width + width / 2

    def find_way_old(self, world, me):
        width = 100
        n, m = int(800 / width / 2), int(800 / width / 2 - 1)
        k = int(800 / width - 1)
        stop_x = int(clamp((self.target_point_x - self.x + 400) // width, 0, k))
        stop_y = int(clamp((self.target_point_y - self.y + 400) // width, 0, k))
        area = [[0 for i in range(int(800 / width))] for j in range(int(800 / width))]
        for i in world.buildings:
            if me.get_distance_to(i.x, i.y) < 400:
                area[int((i.x - self.x + 400) // width)][int((i.y - self.y + 400) // width)] = 1
        for i in world.minions:
            if me.get_distance_to(i.x, i.y) < 400:
                area[int((i.x - self.x + 400) // width)][int((i.y - self.y + 400) // width)] = 1
        for i in world.wizards:
            if me.get_distance_to(i.x, i.y) < 400:
                area[int((i.x - self.x + 400) // width)][int((i.y - self.y + 400) // width)] = 1
        for i in world.trees:
            if me.get_distance_to(i.x, i.y) < 400:
                area[int((i.x - self.x + 400) // width)][int((i.y - self.y + 400) // width)] = 1
        area[m][m] = 0
        area[m][n] = 0
        area[n][m] = 0
        area[n][n] = 0
        self.area = copy.deepcopy(area) # debug
        self.width = width # debug
        if self.x < self.target_point_x:
            if self.y < self.target_point_y:
                start_x, start_y = n, n
            else:
                start_x, start_y = m, n
        else:
            if self.y < self.target_point_y:
                start_x, start_y = m, n
            else:
                start_x, start_y = m, m
        points = [[start_x, start_y]]
        index = 1
        break_flag = True
        # bfs
        while break_flag and len(points) != 0:
            index += 1
            add_to_points = []
            for i in points:
                x, y = i[0], i[1]
                if x == stop_x and y == stop_y:
                    break_flag = False
                    break
                area[x][y] = index - 1
                if x != k:
                    if area[x+1][y] == 0:
                        area[x+1][y] = index
                        add_to_points.append([x+1, y])
                    if y != k:
                        if area[x+1][y+1] == 0:
                            area[x+1][y+1] = index
                            add_to_points.append([x+1, y+1])
                    if y != 0:
                        if area[x+1][y-1] == 0:
                            area[x+1][y-1] = index
                            add_to_points.append([x+1, y-1])
                if x != 0:
                    if area[x-1][y] == 0:
                        area[x-1][y] = index
                        add_to_points.append([x-1, y])
                    if y != k:
                        if area[x-1][y+1] == 0:
                            area[x-1][y+1] = index
                            add_to_points.append([x-1, y+1])
                    if y != 0:
                        if area[x-1][y-1] == 0:
                            area[x-1][y-1] = index
                            add_to_points.append([x-1, y-1])
                if y != k:
                    if area[x][y+1] == 0:
                        area[x][y+1] = index
                        add_to_points.append([x, y+1])
                if y != 0:
                    if area[x][y-1] == 0:
                        area[x][y-1] = index
                        add_to_points.append([x, y-1])
            points = add_to_points

        # find way in array
        way = []
        index = area[stop_x][stop_y]
        x, y = stop_x, stop_y
        if index > 1:
            while index != 2:
                index -= 1
                if x != k:
                    if area[x + 1][y] == index:
                        x, y = x + 1, y
                        continue
                    if y != k:
                        if area[x + 1][y + 1] == index:
                            x, y = x + 1, y + 1
                            continue
                    if y != 0:
                        if area[x + 1][y - 1] == index:
                            x, y = x + 1, y - 1
                            continue
                if x != 0:
                    if area[x - 1][y] == index:
                        x, y = x - 1, y
                        continue
                    if y != k:
                        if area[x - 1][y + 1] == index:
                            x, y = x - 1, y + 1
                            continue
                    if y != 0:
                        if area[x - 1][y - 1] == index:
                            x, y = x - 1, y - 1
                            continue
                if y != k:
                    if area[x][y + 1] == index:
                        x, y = x, y + 1
                        continue
                if y != 0:
                    if area[x][y - 1] == 0:
                        x, y = x, y - 1
                        continue

        return x * width - 400 + self.x + width / 2, y * width - 400 + self.y + width / 2

    def debug_func(self, world):
        if debug:
            area = self.area
            width = self.width
            with debug.pre() as dbg:
                for i in self.lane_array_BOTTOM:
                    radius = 5
                    if i == self.lane_array_BOTTOM[self.lane_point_index]:
                        radius = 25
                    dbg.fill_circle(i[0], i[1], radius, Color(r=1.0, g=0.0, b=0.0))
                for i in range(len(area)):
                    for j in range(len(area)):
                        if area[i][j] == 0:
                            dbg.rect((i + self.x_cage_offset) * width, (j + self.y_cage_offset) * width,
                                     (i + 1 + self.x_cage_offset) * width, (j + 1 + self.y_cage_offset) * width,
                                     Color(r=0.0, g=0.0, b=0.0))
                        else:
                            dbg.fill_rect((i + self.x_cage_offset) * width, (j + self.y_cage_offset) * width,
                                          (i + 1 + self.x_cage_offset) * width, (j + 1 + self.y_cage_offset) * width,
                                          Color(r=0.0, g=0.0, b=0.0))
            with debug.post() as dbg:
                dbg.fill_circle(self.step_point_x, self.step_point_y, 10, Color(r=0.0, g=1.0, b=0.0))
