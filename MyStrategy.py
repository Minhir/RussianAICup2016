from model.Game import Game
from model.Move import Move
from model.Wizard import Wizard
from model.World import World
from model.LaneType import LaneType
from model.ActionType import ActionType
from model.Faction import Faction
from random import uniform, choice
from math import sin, cos, fabs, pi
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
        self.prev_status = None
        # ------------------------------
        self.lane = None
        self.x, self.y = None, None
        self.lane_point_index = 0
        self.target_point_x, self.target_point_y = None, None
        self.step_point_x, self.step_point_y = None, None
        self.last5step = [[1, 2], [3, 4], [5, 6], [7, 8], [9, 10]]
        self.stuck_start_tick = None
        self.status = "go"   # "go", "fight", "stuck", "escape"
        self.faction = None
        self.enemy_faction = None

    # ------------------------------------------------------------------------

    def move(self, me: Wizard, world: World, game: Game, move: Move):
        if world.tick_index == 0:
            self.init(me)
            return

        #c = time()
        self.x = me.x
        self.y = me.y

        self.check_stuck()
        if self.status == "stuck":
            self.get_out(move, game, world.tick_index)

        if self.status != "stuck":
            self.check_danger(me)
            if self.status == "escape":
                self.map_master(-1)
                self.step_point_x, self.step_point_y = self.find_way(world, me)
                self.go(me, move, game)

        if self.status != "stuck" or self.status != "escape":
            enemy = self.situation_analysis(world, me)
            if self.status == "fight":
                self.attack(move, game, me, enemy)

        if self.status == "go":
            if me.get_distance_to(self.target_point_x, self.target_point_y) < 200:
                self.map_master(1)
            self.step_point_x, self.step_point_y = self.find_way(world, me)
            self.go(me, move, game)

        # debug
        self.debug_func(world)
        if self.prev_status != self.status:
            print(self.status)
            self.prev_status = self.status

    # ------------------------------------------------------------------------

    def attack(self, move, game, me, enemy):
        if enemy is None:
            return
        angle = me.get_angle_to(enemy.x, enemy.y)
        move.turn = angle
        if fabs(angle) < game.staff_sector / 2:
            move.cast_angle = angle
            move.min_cast_distance = me.get_distance_to(enemy.x, enemy.y) #- enemy.radius + game.getMagicMissileRadius
            move.action = ActionType.MAGIC_MISSILE

    def check_danger(self, me):
        if me.life < me.max_life * 0.5:
            self.status = "escape"

    def check_stuck(self):
        if self.status == "stuck" or self.status == "fight":
            return
        for i in range(4):
            self.last5step[i][0] = self.last5step[i + 1][0]
            self.last5step[i][1] = self.last5step[i + 1][1]
        self.last5step[4] = [self.x, self.y]
        for i in range(3):
            if self.last5step[i] != self.last5step[i + 1]:
                break
        else:
            self.status = "stuck"

    def find_way(self, world, me):
        width = 50
        area_len = int(800 / width - 1)
        if self.x > 400:
            x_cage_offset = int((self.x - 400) // width)
        else:
            x_cage_offset = int((self.x - 400) // width) + 1
        if self.y > 400:
            y_cage_offset = int((self.y - 400) // width)
        else:
            y_cage_offset = int((self.y - 400) // width) + 1
        stop_x = int(clamp(self.target_point_x // width - x_cage_offset, 0, area_len))
        stop_y = int(clamp(self.target_point_y // width - y_cage_offset, 0, area_len))
        area = [[0 for i in range(int(800 / width))] for j in range(int(800 / width))]
        for i in world.minions + world.buildings + world.trees + world.wizards:
            if (me.get_distance_to(i.x, i.y) > 400 - width) or (i.x == me.x and i.y == me.y):
                continue
            add_radius_x = []
            add_radius_y = []
            for j in range(int((i.radius + me.radius) // width)):
                for k in [pi/12*x for x in range(-12, 13)]:
                    add_radius_x.append((j + 1) * width * sin(k))
                    add_radius_y.append((j + 1) * width * cos(k))
            add_radius_x.append(0)
            add_radius_y.append(0)
            for j in range(len(add_radius_x)):
                if me.get_distance_to(i.x + add_radius_x[j], i.y + add_radius_y[j]) < 400 - width:
                    area[int((i.x + add_radius_x[j]) // width - x_cage_offset)][int((i.y + add_radius_y[j]) // width - y_cage_offset)] = 1

        area[int(self.x // width - x_cage_offset)][int(self.y // width - y_cage_offset)] = 0
        # ------------------------------------
        self.area = copy.deepcopy(area) # debug
        self.width = width # debug
        self.x_cage_offset = x_cage_offset
        self.y_cage_offset = y_cage_offset
        # ------------------------------------
        points = [[int(self.x // width - x_cage_offset), int(self.y // width - y_cage_offset)]]  # Start points... ???
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
                if x != area_len:
                    if area[x+1][y] == 0:
                        area[x+1][y] = index
                        add_to_points.append([x+1, y])
                    if y != area_len:
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
                    if y != area_len:
                        if area[x-1][y+1] == 0:
                            area[x-1][y+1] = index
                            add_to_points.append([x-1, y+1])
                    if y != 0:
                        if area[x-1][y-1] == 0:
                            area[x-1][y-1] = index
                            add_to_points.append([x-1, y-1])
                if y != area_len:
                    if area[x][y+1] == 0:
                        area[x][y+1] = index
                        add_to_points.append([x, y+1])
                if y != 0:
                    if area[x][y-1] == 0:
                        area[x][y-1] = index
                        add_to_points.append([x, y-1])
            points = add_to_points

        # find way in array
        index = area[stop_x][stop_y]
        x, y = stop_x, stop_y
        self.zhopa = []
        if index > 1:
            while index != 2:
                self.zhopa.append([x, y])
                index -= 1
                if y != area_len:
                    if area[x][y + 1] == index:
                        x, y = x, y + 1
                        continue
                if y != 0:
                    if area[x][y - 1] == 0:
                        x, y = x, y - 1
                        continue
                if x != area_len:
                    if area[x + 1][y] == index:
                        x, y = x + 1, y
                        continue
                    if y != area_len:
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
                    if y != area_len:
                        if area[x - 1][y + 1] == index:
                            x, y = x - 1, y + 1
                            continue
                    if y != 0:
                        if area[x - 1][y - 1] == index:
                            x, y = x - 1, y - 1
                            continue
        return (x + x_cage_offset) * width + width / 2, (y + y_cage_offset) * width + width / 2

    def get_out(self, move, game, tick):
        if self.stuck_start_tick is None:
            self.stuck_start_tick = tick
        elif tick - self.stuck_start_tick > 20:
            self.status = "go"
            self.stuck_start_tick = None
            return True
        move.speed = -game.wizard_forward_speed
        move.turn = uniform(-game.wizard_max_turn_angle, game.wizard_max_turn_angle)
        return False

    def go(self, me, move, game):
        move.turn = clamp(me.get_angle_to(self.step_point_x, self.step_point_y),
                          -game.wizard_max_turn_angle, game.wizard_max_turn_angle)
        move.speed = game.wizard_forward_speed * (1 - 0.5 * move.turn / game.wizard_max_turn_angle)
        # move.strafe_speed += game.wizard_strafe_speed * sin(0.05 * tick) * 0.2

    def init(self, me):
        self.status = "go"
        self.lane = choice([LaneType.BOTTOM, LaneType.MIDDLE, LaneType.TOP])
        self.x = me.x
        self.y = me.y
        self.target_point_x, self.target_point_y = self.x, self.y
        self.faction = me.faction
        if self.faction == Faction.ACADEMY:
            self.enemy_faction = Faction.RENEGADES
        else:
            self.enemy_faction = Faction.ACADEMY

    def map_master(self, direction):
        if self.lane == LaneType.BOTTOM:
            self.lane_point_index = clamp(self.lane_point_index + direction, 0, 17)
            if self.lane_point_index <= 8:
                self.target_point_x = self.lane_point_index * 400 + 250
                self.target_point_y = 3750
            else:
                self.target_point_x = 3750
                self.target_point_y = 4000 - (self.lane_point_index - 8) * 400 - 250
        elif self.lane == LaneType.MIDDLE:
            self.lane_point_index = clamp(self.lane_point_index + direction, 0, 9)
            self.target_point_x = self.lane_point_index * 400 + 250
            self.target_point_y = 4000 - self.lane_point_index * 400 - 250
        elif self.lane == LaneType.TOP:
            self.lane_point_index = clamp(self.lane_point_index + direction, 0, 17)
            if self.lane_point_index <= 8:
                self.target_point_x = 200
                self.target_point_y = 4000 - self.lane_point_index * 400 - 250
            else:
                self.target_point_x = (self.lane_point_index - 8) * 400 + 250
                self.target_point_y = 250

    def situation_analysis(self, world, me):
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

    # ------------------------------------------------------------------------

    def debug_func(self, world):
        if debug:
            area = self.area
            width = self.width
            with debug.pre() as dbg:
                for i in self.zhopa:
                    dbg.fill_circle((i[0]+ self.x_cage_offset) * width + width/2, (i[1] + self.y_cage_offset) * width + width/2, 10, Color(r=0.0, g=0.0, b=1.0))
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
                dbg.fill_circle(self.target_point_x, self.target_point_y, 20, Color(r=1.0, g=0.0, b=0.0))
