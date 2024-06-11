import sys
import string
import random
import json

import pygame
from pygame.locals import *

from macvar import dir_ego

from coordinate import (
    INV_WIDTH, INV_HEIGHT,
    GRID_WIDTH, GRID_HEIGHT,
    pos2grid_num,
    grid_num2pos,
    itemname2gridnum,
    pattern2name,
    recipes,
)

from functions import (
    is_synthesizable,
    write_video,
)

num2name = dict(zip(itemname2gridnum.values(), itemname2gridnum.keys()))


# 初始化Pygame
pygame.init()

# 设置屏幕尺寸和显示模式
vec = pygame.math.Vector2
HEIGHT, WIDTH = INV_HEIGHT + 150, INV_WIDTH + 150
CURSOR_HEIGHT, CURSOR_WIDTH = 20, 12
# drag parameters
ACC, FRIC = 1.0, -0.24  # ACC, FRIC = 0.5, -0.12
FPS = 40

''' left top point of inventory image '''
inv_x, inv_y = (WIDTH - INV_WIDTH) // 2, (HEIGHT - INV_HEIGHT) // 2

FramePerSecond = pygame.time.Clock()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Minecraft Crafting Interface")

# 加载图像资源
cursor_image = pygame.image.load(f"{dir_ego}/resources/custom_cursor.png")
cursor_image = pygame.transform.scale(cursor_image, (20, 12)) 
cursor_rect = cursor_image.get_rect()


class ActionHolder:

    def __init__(self):
        self.store_key = {K_LSHIFT: False}
        pass

    def get_action(self, fmt='dict'):
        action = {'accx': 0, 'accy': 0, 'drag': 0}
        pressed_key = pygame.key.get_pressed()
        # action-drag
        if pressed_key[K_LSHIFT]:
            if not self.store_key[K_LSHIFT]:
                ''' jump True '''
                action['drag'] = 1
        # action-accx
        if pressed_key[K_LEFT] and not pressed_key[K_RIGHT]:
            action['accx'] = -1
        elif not pressed_key[K_LEFT] and pressed_key[K_RIGHT]:
            action['accx'] = 1
        # action-accy
        if pressed_key[K_UP] and not pressed_key[K_DOWN]:
            action['accy'] = -1
        elif not pressed_key[K_UP] and pressed_key[K_DOWN]:
            action['accy'] = 1
        
        self.store_key[K_LSHIFT] = True if pressed_key[K_LSHIFT] else False
        if fmt == 'dict':
            return action
        elif fmt == 'list':
            return [action['accx'], action['accy'], action['drag']]


''' 动态精灵 '''
class Cursor(pygame.sprite.Sprite):

    def __init__(self) -> None:
        super().__init__()
        cursor_image = pygame.image.load(f"{dir_ego}/resources/custom_cursor.png")
        self.surf = pygame.transform.scale(cursor_image, (CURSOR_WIDTH, CURSOR_HEIGHT)) 
        self.rect = self.surf.get_rect()

        self.pos = vec((WIDTH // 2, HEIGHT // 2))
        self.vel = vec(0, 0)
        self.acc = vec(0, 0)

    def move(self, action):
        self.acc.x = action['accx']
        self.acc.y = action['accy']

        # friction 
        self.acc += self.vel * FRIC

        # vecility
        self.vel += self.acc
        self.pos += self.vel + 0.5 * self.acc

        if self.pos.x > WIDTH:
            self.pos.x = 0
        if self.pos.y > HEIGHT:
            self.pos.y = 0
        if self.pos.x < 0:
            self.pos.x = WIDTH
        if self.pos.y < 0:
            self.pos.y = HEIGHT

        self.rect.center = vec(self.pos.x + CURSOR_WIDTH//2, self.pos.y + CURSOR_HEIGHT//2)


''' 静态精灵 '''
class Inventory(pygame.sprite.Sprite):

    def __init__(self):
        super().__init__()
        cursor_image = pygame.image.load(f"{dir_ego}/resources/Inventory3_3.png")
        self.surf = cursor_image
        self.rect = self.surf.get_rect(center=(WIDTH/2, HEIGHT/2))


class Item(pygame.sprite.Sprite):

    def __init__(self, item_name, grid_num=0):
        super().__init__()
        self.id = ''.join(random.sample(string.ascii_letters, k=10))
        self.item_name = item_name
        item_image = pygame.image.load(f"{dir_ego}/resources/{item_name}.png")
        self.surf = pygame.transform.scale(item_image, (GRID_WIDTH, GRID_HEIGHT))

        if self.item_name in itemname2gridnum:
            self.grid_num = itemname2gridnum[self.item_name]
        else:
            self.grid_num = grid_num
        x, y = grid_num2pos(self.grid_num, True)
        self.rect = self.surf.get_rect(center=(x + inv_x, y + inv_y))

    def update_rect(self, x, y):
        self.rect = self.surf.get_rect(center=(x, y))

    def update_pos(self, num):
        if 0 <= num < 10 or 16 < num < 26:
            self.grid_num = num
            x, y = grid_num2pos(num, True)
            self.rect = self.surf.get_rect(center=(x + inv_x, y + inv_y))


class ItemGroup:

    def __init__(self):
        self.group = []
        self.dragged = None
        self.synthe = None

    def find_pos(self, num):
        for i, item in enumerate(self.group):
            if item.grid_num == num:
                return i
        return -1
    
    def check_syn(self,):
        # ''' check pattern '''
        # pat = [None] * 9
        # for item in self.group:
        #     pat[item.grid_num - 1] = item
        # patstr = ''.join([' ' if item == None else '#' for item in pat])
        # if patstr not in pattern2name:
        #     return None
        # pat_name = pattern2name[patstr]

        # ''' check color '''
        # if pat_name == 'axe' or pat_name == 'hoe':
        #     if pat[4].item_name != pat[7].item_name:
        #         return None
        # if pat[7].item_name not in ['']

        # ''' check material '''
        cftable = {item.grid_num - 1: item.item_name for item in self.group}
        return is_synthesizable(recipes, cftable)
    
    def exist_item(self, item_name):
        for i, item in enumerate(self.group):
            if item.item_name == item_name:
                return True      
        return False


class JungingEnv:

    def __init__(self) -> None:
        ''' initialize components:
                1. cursor
                2. dynamic icons, including dragged icon
                3. static icons and background surface '''
        self.cursor = Cursor()
        self.group = ItemGroup()
        self.inv = ItemGroup()

        # static images
        self.groups_static = pygame.sprite.Group()
        self.groups_static.add(Inventory())
        for item_name in itemname2gridnum:
            sp = Item(item_name)
            self.groups_static.add(sp)
        pass

        self.timestep = 0
        self.task = None

    def set_task(self, task_name, timelimit):
        self.task = (task_name, timelimit)

    def check_task(self):
        if self.task == None:
            return False, ''
        if self.inv.exist_item(self.task[0]):
            return True, 'finish'
        if self.timestep > self.task[1] * FPS:
            return True, 'timeout'
        return False, ''

    def reset(self, ):
        
        pass

    def step(self, action):
        ''' 
            action:
                accx = -1, 0, 1
                accy = -1, 0, 1
                drag = 0, 1 
        '''
        self.cursor.move(action)
        vx, vy = self.cursor.pos.x, self.cursor.pos.y
        # position grid num if cursor in grids
        num = pos2grid_num(vx - inv_x, vy - inv_y)

        if action['drag']:
            print(f'x: {self.cursor.pos.x}, y: {self.cursor.pos.y}')

        # cursor hove on grids
        if action['drag'] and num != None and 0 < num < 16:
            # cursor hove on dynamic icons, return idx of self.group.group
            idx = self.group.find_pos(num)
            dragged = self.group.dragged
            print(f'drag none: {dragged == None}, idx: {idx}, num: {num}, group-len: {len(self.group.group)}')

            # case01, not dragged, hover on materials
            # dragged up, <- done ->
            if dragged == None and 9 < num < 16:
                print('case01')
                self.group.dragged = Item(num2name[num])

            # case02, dragged, hover on same material
            # clear dragged, <- done ->
            elif dragged != None and num in num2name and \
                num2name[num] == self.group.dragged.item_name:
                print('case02')
                self.group.dragged = None

            # case03, dragged, hover on diff material
            # dragged up, <- done ->
            elif dragged != None and num in num2name and \
                num2name[num] != self.group.dragged.item_name:
                print('case03')
                self.group.dragged = Item(num2name[num])

            # case05, not dragged, hover on icon
            # dragged up, clean icon's grid, <- done ->
            elif dragged == None and idx > -1:
                print('case05')
                self.group.dragged = self.group.group.pop(idx)

            # case06, dragged, hover on empty table
            # put down, <- done ->
            elif dragged != None and 0 < num < 10 and idx < 0:
                print('case06')
                item_name = self.group.dragged.item_name
                new_item = Item(item_name)
                new_item.update_pos(num)
                self.group.group.append(new_item)

            # case07, dragged, hover on same icon
            # clean icon's grid, <- bug ->
            elif dragged != None and idx > -1 and \
                self.group.group[idx].item_name == self.group.dragged.item_name:
                print('case07')
                self.group.group.pop(idx)

            # case08, dragged, hover on diff icon
            # switch icons, <- bug ->
            elif dragged != None and idx > -1 and \
                self.group.group[idx].item_name != self.group.dragged.item_name:
                print('case08')
                item_name = self.group.group[idx].item_name
                self.group.dragged.update_pos(num)
                self.group.group[idx] = self.group.dragged
                self.group.dragged = Item(item_name)

        elif action['drag'] and num != None and 16 < num < 26:
            # case01: dragged, put in empty invtory
            pos = self.inv.find_pos(num)
            if self.group.dragged != None and pos < 0:
                print('case16')
                dragged = self.group.dragged
                dragged.update_pos(num)
                self.inv.group.append(dragged)
                self.group.dragged = None
            elif self.group.dragged == None and pos >= 0:
                self.group.dragged = self.inv.group.pop(pos)
            
            # case02: 
                pass

        # synthesize
        elif action['drag'] and num == 16 and self.group.dragged == None:
            ''' check synthe, show new item '''
            syn_name = self.group.check_syn()
            if syn_name != None:
                self.group.synthe = Item(syn_name, 0)
            pass
        
        # drag up the result item
        elif action['drag'] and num == 0 and self.group.dragged == None:
            ''' clear result and table '''
            self.group.group = []
            if self.group.synthe != None:
                self.group.dragged = self.group.synthe
            self.group.synthe = None

        if self.group.dragged != None:
            self.group.dragged.update_rect(
                self.cursor.pos.x,
                self.cursor.pos.y
            )
        self.timestep += 1
        self.render()
        rgb = pygame.surfarray.array3d(screen)
        return rgb.swapaxes(1, 0)

    def render(self):

        screen.fill((168, 168, 168))
        for entity in self.groups_static:
            screen.blit(entity.surf, entity.rect)
        
        for entity in self.group.group:
            screen.blit(entity.surf, entity.rect)
        for entity in self.inv.group:
            screen.blit(entity.surf, entity.rect)
        syned = self.group.synthe
        if syned != None:
            screen.blit(syned.surf, syned.rect)     
        dragged = self.group.dragged
        if dragged != None:
            screen.blit(dragged.surf, dragged.rect)    
        screen.blit(self.cursor.surf, self.cursor.rect)

        # add task info
        if self.task != None:
            task_name = self.task[0]
            goal_font = pygame.font.SysFont('Comic Sans MS', 30)
            text = goal_font.render('Goal:', 1, (255, 255, 255))
            screen.blit(text, (20, 20))
            icon = Item(task_name)
            icon.update_rect(110, 40)
            screen.blit(icon.surf, icon.rect)

        if self.task != None and self.task[1] > 0:
            timelimit = self.task[1]
            time_font = pygame.font.SysFont('Comic Sans MS', 30)
            text = time_font.render(f'Time: {self.timestep // FPS}/{timelimit}', 1, (255, 255, 255))
            screen.blit(text, (200, 20))

        pygame.display.update()
        

class UserModel:

    def __init__(self) -> None:
        self.env = JungingEnv()
        self.holder = ActionHolder()  # listen user action
        self.frames = []
        self.actions = []
        self.finish = False
        pass

    def set_task(self, task_name, timelimit):
        self.env.set_task(task_name, timelimit)

    def interact(self, ):

        while True:
            qt = False
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    qt = True
                    break
                elif event.type == pygame.KEYUP:
                    if event.key == pygame.K_ESCAPE:
                        pygame.quit()
                        qt = True
                        break
            if qt:
                break
            action = self.holder.get_action()
            rgb = self.env.step(action)

            state = self.env.check_task()
            
            self.actions.append(action)
            self.frames.append(rgb)
            
            FramePerSecond.tick(FPS)

            if state[0]:
                if state[1] == 'finish':
                    print(f'Task finished with {self.env.timestep // FPS} seconds.')
                    self.finish = True
                else:
                    print('Time out.')
                pygame.quit()
                break
            
    def save_video(self, name):
        name = f'{name}-done' if self.finish else name
        video_path = f'{dir_ego}/outputs/{name}.mp4'
        write_video(self.frames, video_path, (WIDTH, HEIGHT), FPS)

        action_path = f'{dir_ego}/outputs/{name}.json'
        with open(action_path, 'w') as f:
            json.dump(self.actions, f)


def get_rand_task():
    color = random.choice(['red', 'green', 'blue'])
    material = random.choice(['diamond', 'iron', 'wooden'])
    shape = random.choice(['axe', 'hoe', 'sword'])
    return f'{color}_{material}_{shape}'


if __name__ == '__main__':

    model = UserModel()
    model.set_task('blue_wooden_sword', 60)
    model.interact()
    model.save_video('record0611-blue_wooden_sword-v01')
