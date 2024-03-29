from model.Game import Game
from model.Move import Move
from model.Wizard import Wizard
from model.World import World
from model.LaneType import LaneType
from model.ActionType import ActionType
from model.Faction import Faction
from model.MinionType import MinionType
from model.Message import Message
from random import choice, random
from math import sin, cos, fabs, pi
import copy


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
        self.area_cope = []  # debug
        self.width = None
        self.x_cage_offset = None
        self.y_cage_offset = None
        self.for_debug_start = None
        # ------------------------------
        self.lane = None
        self.x, self.y = None, None
        self.lane_point_index = 0
        self.min_distance_to_enemy = float("inf")
        self.target_point_x, self.target_point_y = None, None
        self.step_point_x, self.step_point_y = None, None
        self.last5step = [[1, 2], [3, 4], [5, 6], [7, 8], [9, 10]]  # for stuck check
        self.stuck_start_tick = None
        self.faction = None
        self.enemy_faction = None
        self.is_fight = False
        self.last_tick = 0
        self.get_out_bin = 1
        self.sin_table = [sin(pi/18*x) for x in range(-18, 19)]
        self.cos_table = [cos(pi/18*x) for x in range(-18, 19)]
        self.way_trajectory = []
        self.enemy_towers_coordinates = []
        self.enemy_towers_status = [True, True, True, True, True, True]  # Top1, Top2, Mid1, Mid2, Bot1, Bot2
        self.waypoints_TOP, self.waypoints_MID, self.waypoints_BOT = [], [], []
        self.wait_status = False

    def move(self, me: Wizard, world: World, game: Game, move: Move):
        if world.tick_index == 0:
            self.init(me, move, world)
            return
        if world.tick_index < 500 and not me.master:
            if me.messages:
                for m in me.messages:
                    self.lane = m.lane
        if world.tick_index == 500 and self.lane is None:
            self.lane_analysis(world)

        self.last_tick = world.tick_index
        move.speed = 0
        move.strafe_speed = 0
        move.turn = 0
        self.x = me.x
        self.y = me.y
        self.tower_analysis(world)

        if world.tick_index - self.last_tick > 500:  # check death
            self.lane_point_index = 0
            self.stuck_start_tick = None
            self.is_fight = False
            self.lane_analysis(world)

        # Stuck
        if self.check_stuck(world.tick_index):
            self.get_out(move, game)
            self.debug_func(world)  # debug
            print("stuck")
            return

        # Escape
        if self.check_danger(me):
            if self.check_if_enemy_near(world, me, game):
                self.map_master(-1, me)
            else:
                # self.map_master(1, me)
                self.wait_status = True
                return
            self.step_point_x, self.step_point_y = self.find_way(world, me)
            self.go(me, move, game)
            self.debug_func(world)  # debug
            print("escape")
            return

        # Fight
        # TODO: уклонение от вражеских снарядов,
        # TODO: хитрая система отхода с максимзацией получаемого опыта
        # TODO: удар посохом
        # TODO: учёт бонусов на врагах
        # TODO: не всегда стрелять!?
        self.is_fight, enemy, distance_to_closest_minion, tower_near, wizards_amount = self.situation_analysis(world, me)
        if self.is_fight:
            self.attack(move, game, me, enemy)
            if (me.life < me.max_life*0.5) or \
                    (distance_to_closest_minion < 200) or \
                    ((type(enemy) is Wizard) and (me.life < enemy.life)) or \
                    (wizards_amount > 1):
                self.map_master(-1, me)
                self.step_point_x, self.step_point_y = self.find_way(world, me)
                self.go_back(me, move, game)
            else:
                if distance_to_closest_minion > 500 - 380 * (me.life / me.max_life)**2:
                    if not tower_near and (wizards_amount <= 1) and (type(enemy) is not MinionType.FETISH_BLOWDART):
                        self.target_point_x, self.target_point_y = enemy.x, enemy.y
                        self.step_point_x, self.step_point_y = self.find_way(world, me)
                        self.go(me, move, game)
            self.debug_func(world)  # debug
            print("fight")
            return

        # GO
        if world.tick_index < 1500 - int(self.lane == LaneType.MIDDLE) * 250:  # wait for minions
            if me.y < 450 + me.x:
                self.map_master(-1, me)
            else:
                self.map_master(1, me)
        else:
            self.map_master(1, me)
        self.step_point_x, self.step_point_y = self.find_way(world, me)
        self.go(me, move, game)
        self.debug_func(world)  # debug
        print("GO")

    def attack(self, move, game, me, enemy):
        # TODO: предсказание положения врага
        if enemy is None:
            return
        angle = me.get_angle_to(enemy.x, enemy.y)
        move.turn = angle
        if fabs(angle) < game.staff_sector / 2:
            move.cast_angle = angle
            move.min_cast_distance = me.get_distance_to(enemy.x, enemy.y)
            move.action = ActionType.MAGIC_MISSILE

    def check_danger(self, me):
        # TODO: производную по жизням
        if me.life < me.max_life * 0.3:
            return True
        else:
            return False

    def check_if_enemy_near(self, world, me, game):
        for i in world.wizards + world.buildings:
            if i.faction == self.enemy_faction:
                if me.get_distance_to(i.x, i.y) < game.wizard_vision_range:
                    return True
        for i in world.minions:
            if i.faction == self.enemy_faction:
                if me.get_distance_to(i.x, i.y) < 400:
                    return True
        for i in range(6):
            if self.enemy_towers_status[i]:
                if me.get_distance_to(self.enemy_towers_coordinates[i][0], self.enemy_towers_coordinates[i][1]) < 700:
                    return True
        return False

    def check_stuck(self, tick):
        if self.stuck_start_tick is None:
            if self.is_fight or self.wait_status:
                return False
            for i in range(4):
                self.last5step[i][0] = self.last5step[i + 1][0]
                self.last5step[i][1] = self.last5step[i + 1][1]
            self.last5step[4] = [self.x, self.y]
            for i in range(3):
                if self.last5step[i] != self.last5step[i + 1]:
                    return False
            else:
                self.stuck_start_tick = tick
                return True
        elif tick - self.stuck_start_tick > 15:
            self.get_out_bin *= -1
            self.stuck_start_tick = None
            return False
        else:
            return True

    def find_way(self, world, me):
        width = 20
        cage_length = 800
        half_cage_length = cage_length / 2
        area_len = int(cage_length / width - 1)
        if self.x > half_cage_length:
            x_cage_offset = int((self.x - half_cage_length) // width)
        else:
            x_cage_offset = int((self.x - half_cage_length) // width) + 1
        if self.y > half_cage_length:
            y_cage_offset = int((self.y - half_cage_length) // width)
        else:
            y_cage_offset = int((self.y - half_cage_length) // width) + 1
        stop_x = int(clamp(self.target_point_x // width - x_cage_offset, 0, area_len))
        stop_y = int(clamp(self.target_point_y // width - y_cage_offset, 0, area_len))
        area = [[0 for i in range(int(cage_length / width))] for j in range(int(cage_length / width))]
        for i in world.minions + world.buildings + world.trees + world.wizards:
            if (me.get_distance_to(i.x, i.y) > half_cage_length - width) or (i.x == me.x and i.y == me.y):
                continue
            add_radius_x = []
            add_radius_y = []
            for j in range(1, int((i.radius + me.radius + 0.01) // width) + 1):
                for k in range(-18, 19):
                    add_radius_x.append((j * width) * self.sin_table[k])
                    add_radius_y.append((j * width) * self.cos_table[k])
            add_radius_x.append(0)
            add_radius_y.append(0)
            for j in range(len(add_radius_x)):
                if me.get_distance_to(i.x + add_radius_x[j], i.y + add_radius_y[j]) < half_cage_length - width:
                    area[int((i.x + add_radius_x[j]) // width - x_cage_offset)][int((i.y + add_radius_y[j]) // width - y_cage_offset)] = -1
        # detect "walls"
        for i in range(int(cage_length / width)):
            for j in range(int(cage_length / width)):
                if me.radius < (i + x_cage_offset) * width + width / 2 < world.width - me.radius:
                    pass
                else:
                    area[i][j] = -1
                if me.radius < (j + y_cage_offset) * width + width / 2 < world.width - me.radius:
                    pass
                else:
                    area[i][j] = -1
        area[int(self.x // width - x_cage_offset)][int(self.y // width - y_cage_offset)] = 0
        # ------------------------------------
        self.area_cope = copy.deepcopy(area)  # debug
        self.width = width
        self.x_cage_offset = x_cage_offset
        self.y_cage_offset = y_cage_offset
        # ------------------------------------
        area[int(self.x // width - x_cage_offset)][int(self.y // width - y_cage_offset)] = 1
        start_points = [int(self.x // width - x_cage_offset), int(self.y // width - y_cage_offset)]
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
        # TODO: не ходить зигзагами
        index = area[stop_x][stop_y]
        x, y = stop_x, stop_y
        self.way_trajectory = []
        if index > 1:
            while index != 2:
                self.way_trajectory.append([x, y])
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
        # --------------------------------
        # Find angles in trajectory
        self.way_trajectory.append([x, y])
        self.way_trajectory.append(start_points)
        self.way_trajectory.reverse()
        if len(self.way_trajectory) > 2:
            direction = [self.way_trajectory[1][0] - self.way_trajectory[0][0],
                         self.way_trajectory[1][1] - self.way_trajectory[0][1]]
            for i in range(2, len(self.way_trajectory)):
                current_direction = [self.way_trajectory[i][0] - self.way_trajectory[i - 1][0],
                                     self.way_trajectory[i][1] - self.way_trajectory[i - 1][1]]
                if direction == current_direction:
                    continue
                else:
                    result_x, result_y = self.way_trajectory[i - 1][0], self.way_trajectory[i - 1][1]
                    break
            else:
                result_x, result_y = self.way_trajectory[-1][0], self.way_trajectory[-1][1]
        else:
            result_x, result_y = x, y
        # --------------------------------
        return (result_x + x_cage_offset) * width + width / 2, (result_y + y_cage_offset) * width + width / 2

    def get_out(self, move, game):
        move.speed = -game.wizard_forward_speed * (1 - 0.5 * random())
        move.strafe_speed = game.wizard_strafe_speed * 0.5 * self.get_out_bin
        move.turn = game.wizard_max_turn_angle * self.get_out_bin

    def go(self, me, move, game):
        angle = me.get_angle_to(self.step_point_x, self.step_point_y)
        move.turn = clamp(angle, -game.wizard_max_turn_angle, game.wizard_max_turn_angle)
        move.speed = game.wizard_forward_speed * cos(angle)
        move.strafe_speed = game.wizard_strafe_speed * sin(angle)
        '''speed_vector_length = hypot(move.speed, move.strafe_speed)
        if speed_vector_length > me.get_distance_to(self.step_point_x, self.step_point_y):
            k = speed_vector_length / me.get_distance_to(self.step_point_x, self.step_point_y)
            move.speed /= k
            move.strafe_speed /= k'''

    def go_back(self, me, move, game):
        angle = me.get_angle_to(self.step_point_x, self.step_point_y)
        move.speed = game.wizard_backward_speed * cos(angle)
        move.strafe_speed = game.wizard_strafe_speed * sin(angle)

    def init(self, me, move, world):
        self.x = me.x
        self.y = me.y
        self.target_point_x, self.target_point_y = self.x, self.y
        self.faction = me.faction
        if self.faction == Faction.ACADEMY:
            self.enemy_faction = Faction.RENEGADES
        else:
            self.enemy_faction = Faction.ACADEMY
        if me.master:
            move.messages = [Message(LaneType.MIDDLE, None, None),
                             Message(LaneType.BOTTOM, None, None),
                             Message(LaneType.BOTTOM, None, None),
                             Message(LaneType.BOTTOM, None, None)]
            self.lane = LaneType.TOP
        '''Get enemy towers coordinates. Mirror own towers coordinate.
        for i in world.buildings:
            if i.faction == self.faction:
                [world.width - i.x, world.width - i.y])
        '''
        self.enemy_towers_coordinates = [[1687.8740025771563, 50.0], [2629.339679648397, 350.0],
                                         [2070.710678118655, 1600.0], [3097.386941332822, 1231.9023805485235],
                                         [3650.0, 2343.2513553373133], [3950.0, 1306.7422221916627]]
        for i in range(0, 17):
            if i <= 8:
                self.waypoints_TOP.append([200, 4000 - i * 400 - 250])
                self.waypoints_BOT.append([i * 400 + 250, 3750])
            else:
                self.waypoints_TOP.append([(i - 8) * 400 + 250, 250])
                self.waypoints_BOT.append([3750, 4000 - (i - 8) * 400 - 250])
        for i in range(0, 9):
            self.waypoints_MID.append([i * 400 + 250, 4000 - i * 400 - 250])

    def lane_analysis(self, world):
        # TODO: не идти под трон
        top, mid, bot = 0, 0, 0
        no_top, no_mid, no_bot = False, False, False
        if not self.enemy_towers_status[1]:
            no_top = True
        if not self.enemy_towers_status[3]:
            no_mid = True
        if not self.enemy_towers_status[5]:
            no_bot = True
        for i in world.wizards:
            if i.faction == self.faction and (i.x != self.x and i.y != self.y):
                # Check if wizard in base
                if i.x < 800 and i.y > 3200:
                    continue
                # Count wizards on different lines
                y_2, y_1 = 3200 - i.x, 4800 - i.x
                if i.y < y_2:
                    top += 1
                if y_2 < i.y < y_1:
                    mid += 1
                if i.y > y_1:
                    bot += 1
        if mid == 0 and not no_mid:
            self.lane = LaneType.MIDDLE
            return
        if bot == 0 and not no_bot:
            self.lane = LaneType.BOTTOM
            return
        if top == 0 and not no_top:
            self.lane = LaneType.TOP
        if mid == 1 and not no_mid:
            self.lane = LaneType.MIDDLE
            return
        if bot == 1 and not no_bot:
            self.lane = LaneType.BOTTOM
            return
        if top == 1 and not no_top:
            self.lane = LaneType.TOP
        else:
            self.lane = LaneType.MIDDLE

    def map_master(self, direction, me):
        # TODO: ходьба за руной
        # TODO: смена линий
        def find_next_point(points, me):
            nearest_point = min(points, key=lambda x: me.get_distance_to(x[0], x[1]))
            j = points.index(nearest_point)
            return points[clamp(j + 1, 0, len(points) - 1)]

        def find_prev_point(points, me):
            nearest_point = min(points, key=lambda x: me.get_distance_to(x[0], x[1]))
            j = points.index(nearest_point)
            return points[clamp(j - 1, 0, len(points) - 1)]

        if direction == 1:
            if self.lane == LaneType.BOTTOM:
                self.target_point_x, self.target_point_y = find_next_point(self.waypoints_BOT, me)
            elif self.lane == LaneType.MIDDLE:
                self.target_point_x, self.target_point_y = find_next_point(self.waypoints_MID, me)
            elif self.lane == LaneType.TOP:
                self.target_point_x, self.target_point_y = find_next_point(self.waypoints_TOP, me)
        else:
            if self.lane == LaneType.BOTTOM:
                self.target_point_x, self.target_point_y = find_prev_point(self.waypoints_BOT, me)
            elif self.lane == LaneType.MIDDLE:
                self.target_point_x, self.target_point_y = find_prev_point(self.waypoints_MID, me)
            elif self.lane == LaneType.TOP:
                self.target_point_x, self.target_point_y = find_prev_point(self.waypoints_TOP, me)

    def situation_analysis(self, world, me):
        minions, wizards, buildings = [], [], []
        enemy, tower_near = None, False
        distance_to_closest_minion = float("inf")
        wizards_amount = 0
        for i in world.wizards:
            if i.faction == self.enemy_faction:
                if me.get_distance_to(i.x, i.y) < me.cast_range:
                    wizards.append(i)
        if len(wizards) > 0:
            enemy = min(wizards, key=lambda x: x.life)
            wizards_amount = len(wizards)
        for i in world.buildings:
            if i.faction == self.enemy_faction:
                if me.get_distance_to(i.x, i.y) < me.cast_range:
                    buildings.append(i)
        if len(buildings) > 0:
            tower_near = True
            if enemy is None:
                enemy = min(buildings, key=lambda x: x.life)
        for i in world.minions:
            if i.faction == self.enemy_faction:
                if me.get_distance_to(i.x, i.y) < me.cast_range:
                    minions.append(i)
        if len(minions) > 0:
            closest_minion = min(minions, key=lambda x: me.get_distance_to(x.x, x.y))
            if enemy is None:
                enemy = closest_minion
            distance_to_closest_minion = me.get_distance_to(closest_minion.x, closest_minion.y)
        if enemy is None:
            return False, enemy, distance_to_closest_minion, tower_near, wizards_amount
        else:
            return True, enemy, distance_to_closest_minion, tower_near, wizards_amount

    def tower_analysis(self, world):
        for i in world.wizards + world.minions:
            if i.faction == self.faction:
                for j in range(6):
                    x, y = self.enemy_towers_coordinates[j][0], self.enemy_towers_coordinates[j][1]
                    if self.enemy_towers_status[j] and i.get_distance_to(x, y) < i.vision_range - 10:
                        for k in world.buildings:
                            if fabs(k.x - x) < 10 and fabs(k.y - y) < 10:
                                break
                        else:
                            self.enemy_towers_status[j] = False

    def debug_func(self, world):
        return
        if world.tick_index % 15 != 0:
            return
        if debug:
            area = self.area_cope
            width = self.width

            with debug.pre() as dbg:
                for i in self.way_trajectory:
                    dbg.fill_circle((i[0] + self.x_cage_offset) * width + width / 2,
                                    (i[1] + self.y_cage_offset) * width + width / 2, 10,
                                    Color(r=0.0, g=0.0, b=1.0))
                for i in range(len(area)):
                    for j in range(len(area)):
                        if area[i][j] == 0:
                            dbg.rect((i + self.x_cage_offset) * width,
                                     (j + self.y_cage_offset) * width,
                                     (i + 1 + self.x_cage_offset) * width,
                                     (j + 1 + self.y_cage_offset) * width,
                                     Color(r=0.0, g=0.0, b=0.0))
                        else:
                            dbg.fill_rect((i + self.x_cage_offset) * width,
                                          (j + self.y_cage_offset) * width,
                                          (i + 1 + self.x_cage_offset) * width,
                                          (j + 1 + self.y_cage_offset) * width,
                                          Color(r=0.0, g=0.0, b=0.0))
            with debug.post() as dbg:
                dbg.fill_circle(self.target_point_x, self.target_point_y, 20, Color(r=1.0, g=0.0, b=0.0))
                dbg.fill_circle(self.step_point_x, self.step_point_y, 10, Color(r=0.0, g=1.0, b=0.0))
                for i in range(0, 17):
                    dbg.fill_circle(self.waypoints_TOP[i][0], self.waypoints_TOP[i][1], 40,
                                    Color(r=1.0, g=0.0, b=0.0))
                    dbg.fill_circle(self.waypoints_BOT[i][0], self.waypoints_BOT[i][1], 40,
                                    Color(r=1.0, g=0.0, b=0.0))
                for i in range(0, 9):
                    dbg.fill_circle(self.waypoints_MID[i][0], self.waypoints_MID[i][1], 40,
                                    Color(r=1.0, g=0.0, b=0.0))
                '''for i in range(6):
                    if self.enemy_towers_status[i]:
                        dbg.fill_circle(self.enemy_towers_coordinates[i][0], self.enemy_towers_coordinates[i][1], 40,
                                        Color(r=0.0, g=1.0, b=0.0))
                    else:
                        dbg.fill_circle(self.enemy_towers_coordinates[i][0], self.enemy_towers_coordinates[i][1], 40,
                                        Color(r=1.0, g=0.0, b=0.0))'''
