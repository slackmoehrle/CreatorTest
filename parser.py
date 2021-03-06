#!/usr/bin/python
# ----------------------------------------------------------------------------
# Parses Cocos Creator projects
# ----------------------------------------------------------------------------
'''
Tool that converts Cocos Creator into cocos2d-x
'''
from __future__ import division, unicode_literals, print_function
import sys
import os
import json
import glob
from pprint import pprint
import getopt
from sets import Set
import re


__docformat__ = 'restructuredtext'

# Some globals (yeah!)

# filename of the .fire file to parse
g_filename = ""
# File objects to dump the cpp/h data
g_file_cpp = None
g_file_h = None

# Needed resources
g_resources_needed = set()

# the .fire file being parsed
g_json_data = []

# the .meta files that contain sprite frame info and other data
g_meta_data = {}

# contains the sprite frames: customized version of g_meta_data
# key is the uuid. value is the json container
g_sprite_frames = {}

# sprites that don't belong to any atlas
# should be added to the SpriteFrameCache manually
g_sprite_without_atlas = {}

# sprites that belong to atlas files
# atlas file should be added to the SpriteFrameCache manually
g_sprite_with_atlas = []

# contains the textures used
# key is the uuid. value is the json container
g_textures = {}

# contains the data from library/uuid-to-mtime.json
g_uuid = {}

g_design_resolution = None

# path for the assets
g_assetpath = ""

# global unique id for nodes
# it is just a number that gets incremented with each new node
g_unique_id = 0



def globals_init():
    global g_filename, g_json_data, g_meta_data
    global g_file_cpp, g_file_h
    global g_sprite_frames, g_textures, g_uuid
    global g_sprite_without_atlas, g_sprite_with_atlas
    global g_design_resolution, g_resources_needed
    global g_assetpath
    global g_unique_id

    g_filename = ""
    g_json_data = []
    g_meta_data = {}
    g_sprite_frames = {}
    g_sprite_without_atlas = {}
    g_sprite_with_atlas = []
    g_textures = {}
    g_uuid = {}
    g_design_resolution = None
    g_file_cpp = None
    g_file_h = None
    g_resources_needed = set()
    g_assetpath = ""
    g_unique_id = 0


#
# Node
#
class Node(object):
    @classmethod
    def get_node_components(cls, node):
        idxs = node['_components']
        components = []
        for idx in idxs:
            idx_num = idx['__id__']
            components.append(g_json_data[idx_num])
        return components

    @classmethod
    def get_node_component_of_type(cls, node, t):
        components = Node.get_node_components(node)
        for c in components:
            if c['__type__'] == t:
                return c
        return None

    @classmethod
    def guess_type_from_components(cls, components):
        # ScrollView, Button & ProgressBar should be before Sprite
        supported_components = ('cc.Button', 'cc.ProgressBar', 'cc.ScrollView', 'cc.EditBox', 'cc.Label', 'cc.Sprite', 'cc.ParticleSystem', 'cc.TiledMap', 'cc.Canvas')
        node_components = [x['__type__'] for x in components]
        for supported in supported_components:
            if supported in node_components:
                print("Choosen %s from %s" % (supported, node_components))
                return supported
        print("Unknown components: %s" % node_components)
        return 'unknown'

    @classmethod
    def create_node(cls, node_type, node_idx):
        n = None
        if node_type == 'cc.Sprite':
            n = Sprite(g_json_data[node_idx])
        elif node_type == 'cc.Label':
            n = Label(g_json_data[node_idx])
        elif node_type == 'cc.ParticleSystem':
            n = ParticleSystem(g_json_data[node_idx])
        elif node_type == 'cc.TiledMap':
            n = TiledMap(g_json_data[node_idx])
        elif node_type == 'cc.Canvas':
            n = Canvas(g_json_data[node_idx])
        elif node_type == 'cc.EditBox':
            n = EditBox(g_json_data[node_idx])
        elif node_type == 'cc.ProgressBar':
            n = ProgressBar(g_json_data[node_idx])
        elif node_type == 'cc.Button':
            n = Button(g_json_data[node_idx])
        elif node_type == 'cc.ScrollView':
            n = ScrollView(g_json_data[node_idx])
        if n is not None:
            n.parse_properties()
        return n

    @classmethod
    def get_filepath_from_uuid(self, uuid):
        filepath = None
        if uuid in g_uuid:
            filepath = g_uuid[uuid]['relativePath']
        elif uuid in g_sprite_frames:
            filepath = g_sprite_frames[uuid]['frameName']
        return filepath

    def __init__(self, data):
        self._node_data = data
        self._children = []
        self._properties = {}

        data = self._node_data
        self.add_property_size('setContentSize', "_contentSize", data)
        self.add_property_bool('setEnabled', "_enabled", data)
        self.add_property_str('setName', "_name", data)
        self.add_property_vec2('setAnchorPoint', "_anchorPoint", data)
        self.add_property_bool('setCascadeOpacityEnabled', "_cascadeOpacityEnabled", data)
        self.add_property_rgb('setColor', "_color", data)
        self.add_property_int('setGlobalZOrder', "_globalZOrder", data)
        self.add_property_int('setLocalZOrder', "_localZOrder", data)
        self.add_property_int('setOpacity', "_opacity" , data)
        self.add_property_bool('setOpacityModifyRGB', "_opacityModifyRGB", data)
        self.add_property_vec2('setPosition', "_position", data)
        self.add_property_int('setRotationSkewX', "_rotationX", data)
        self.add_property_int('setRotationSkewY', "_rotationY", data)
        self.add_property_int('setScaleX', "_scaleX", data)
        self.add_property_int('setScaleY', "_scaleY", data)
        self.add_property_int('setSkewX', "_skewX", data)
        self.add_property_int('setSkewY', "_skewY", data)
        self.add_property_int('setTag', "_tag", data)


        self._cpp_node_name = ""
        self._cpp_parent_name = ""

    def add_property(self, newkey, value, keys_to_parse):
        if value in self._node_data:
            new_value = self._node_data.get(value)
            if keys_to_parse is not None:
                new_value = [new_value[k] for k in keys_to_parse]
            self._properties[newkey] = new_value

    def add_property_str(self, newkey, value, data):
        if value in data:
            new_value = data.get(value)
            self._properties[newkey] = '"' + new_value + '"'

    def add_property_size(self, newkey, value, data):
        if value in data:
            w = data.get(value)['width']
            h = data.get(value)['height']
            self._properties[newkey] = 'Size(%g, %g)' % (w,h)

    def add_property_int(self, newkey, value, data):
        if value in data:
            i = data.get(value)
            self._properties[newkey] = i

    def add_property_vec2(self, newkey, value, data):
        if value in data:
            x = data.get(value)['x']
            y = data.get(value)['y']
            self._properties[newkey] = 'Vec2(%g, %g)' % (x,y)

    def add_property_rgb(self, newkey, value, data):
        if value in data:
            r = data.get(value)['r']
            g = data.get(value)['g']
            b = data.get(value)['b']
            self._properties[newkey] = 'Color3B(%d, %d, %d)' %(r,g,b)

    def add_property_bool(self, newkey, value, data):
        if value in data:
            b = str(data.get(value)).lower()
            self._properties[newkey] = b

    def get_class_name(self):
        return type(self).__name__

    def parse_properties(self):
        for child_idx in self._node_data["_children"]:
            self.parse_child(child_idx['__id__'])

    def parse_child(self, node_idx):
        node = g_json_data[node_idx]
        if node['__type__'] == 'cc.Node':
            components = Node.get_node_components(node)
            node_type = Node.guess_type_from_components(components)
            if node_type is not None:
                n = Node.create_node(node_type, node_idx)
                self.adjust_child_parameters(n)
                if n is not None:
                    self.add_child(n)

    def add_child(self, node):
        self._children.append(node)

    def print_scene_graph(self, tab):
        print(self.get_description(tab))
        for child in self._children:
            child.print_scene_graph(tab+2)

    def get_description(self, tab):
        return "%s%s" % ('-' * tab, self.get_class_name())

    def to_cpp(self, parent, depth, sibling_idx):
        self.to_cpp_begin(depth, sibling_idx)
        self.to_cpp_properties()
        self.to_cpp_end()
        if parent is not None:
            parent.to_cpp_add_child(self)

        for idx, child in enumerate(self._children):
            child.to_cpp(self, depth+1, idx)

    def to_cpp_begin(self, depth, sibling_idx):
        global g_unique_id
        g_file_cpp.write("    // New node\n")
        self._cpp_node_name = "%s_%d" % (self.get_class_name().lower(), g_unique_id)
        self._cpp_node_name = self._cpp_node_name.replace(':','')
        g_unique_id = g_unique_id + 1
        g_file_cpp.write("    auto %s = %s::%s;\n" % (self._cpp_node_name, self.get_class_name(), self.to_cpp_create_params()))

    def to_cpp_properties(self):
        for p in self._properties:
            value = self._properties[p]
            g_file_cpp.write("    %s->%s(%s);\n" % (self._cpp_node_name, p, value))

    def to_cpp_end(self):
        '''epilogue'''

    def to_cpp_add_child(self, child):
        '''adds a child to self'''
        g_file_cpp.write("    %s->addChild(%s);\n" % (self._cpp_node_name, child._cpp_node_name))
        g_file_cpp.write("")

    def to_cpp_create_params(self):
        return "create()"

    def adjust_child_parameters(self, child):
        '''Only useful when a parent wants to override some child parameter
           As an example, ScrollView needs to adjust its children position
        '''


################################################################################
#
# Special Nodes: Scene, Canvas
#
################################################################################
class Scene(Node):
    def __init__(self, data):
        super(Scene, self).__init__(data)


class Canvas(Node):
    def __init__(self, data):
        super(Canvas, self).__init__(data)

        component = Node.get_node_component_of_type(self._node_data, 'cc.Canvas')

        global g_design_resolution, g_fit_height, g_fit_width
        g_design_resolution = component['_designResolution']
        g_fit_width = component['_fitWidth']
        g_fit_height = component['_fitHeight']


    # Canvas should be part of the big init
    # but as as part of the scene graph
    # since cocos2d-x doesn't have this concept
    def to_cpp(self, parent, depth, sibling_idx):
        pass

################################################################################
#
# Built-in Renderer Node
# Sprite, Label, TMX, Particle
#
################################################################################
class Sprite(Node):
    SIMPLE, SLICED, TILED, FILLED = range(4)
    def __init__(self, data):
        super(Sprite, self).__init__(data)
        self._sprite_type = Sprite.SIMPLE

    def parse_properties(self):
        super(Sprite, self).parse_properties()

        # search for sprite frame name
        component = Node.get_node_component_of_type(self._node_data, 'cc.Sprite')
        sprite_frame_uuid = component['_spriteFrame']['__uuid__']

#        atlas = component['_atlas']

        # add name between ""
        print(g_sprite_frames[sprite_frame_uuid])
        self.add_property_str('setSpriteFrame', 'frameName', g_sprite_frames[sprite_frame_uuid])
        print(g_sprite_frames[sprite_frame_uuid])

        self._sprite_type = component['_type']
        if self._sprite_type == Sprite.SIMPLE:
            self._properties['setCenterRectNormalized'] = 'Rect(0,0,1,1)'

    def get_description(self, tab):
        return "%s%s('%s')" % ('-' * tab, self.get_class_name(), self._properties['setSpriteFrame'])

    def to_cpp_end(self):
        super(Sprite, self).to_cpp_end()
        if self._sprite_type == Sprite.TILED:
            g_file_cpp.write("    creator_tile_sprite(%s);\n" % self._cpp_node_name)


class Label(Node):

    FONT_SYSTEM, FONT_TTF, FONT_BM = range(3)
    H_ALIGNMENTS = ('TextHAlignment::LEFT', 'TextHAlignment::CENTER', 'TextHAlignment::RIGHT')
    V_ALIGNMENTS = ('TextVAlignment::TOP', 'TextVAlignment::CENTER', 'TextVAlignment::BOTTOM')

    def __init__(self, data):
        super(Label, self).__init__(data)
        self._label_text = ""
        self._font_type = Label.FONT_SYSTEM
        self._font_filename = None

    def parse_properties(self):
        super(Label, self).parse_properties()

        # search for sprite frame name
        component = Node.get_node_component_of_type(self._node_data, 'cc.Label')

        is_system_font = component["_isSystemFontUsed"]
        self._font_size = component['_fontSize']
        self._label_text = component['_N$string']

        # replace new lines with \n
        self._label_text = self._label_text.replace('\n','\\n')

        # alignments
        self._properties['setHorizontalAlignment'] = Label.H_ALIGNMENTS[component['_N$horizontalAlign']]
        self._properties['setVerticalAlignment'] = Label.V_ALIGNMENTS[component['_N$verticalAlign']]

        if is_system_font:
            self._font_type = Label.FONT_SYSTEM
        else:
            self._font_filename = Node.get_filepath_from_uuid(component['_N$file']['__uuid__'])
            if self._font_filename.endswith('.ttf'):
                self._font_type = Label.FONT_TTF
            elif self._font_filename.endswith('.fnt'):
                self._font_type = Label.FONT_BM
                self.add_property_int('setBMFontSize','_fontSize', component)
            else:
                raise Exception("Invalid label file: %s" % filename)

            # needed for multiline. lineHeight not supported in SystemFONT
            self.add_property_int('setLineHeight' ,'_lineHeight', component)

    def to_cpp_create_params(self):
        if self._font_type == Label.FONT_SYSTEM:
            return 'createWithSystemFont("' + self._label_text + '", "arial", ' + str(self._font_size) + ')'
        elif self._font_type == Label.FONT_BM:
            return 'createWithBMFont("' + g_assetpath + self._font_filename + '", "' + self._label_text + '")'
        elif self._font_type == Label.FONT_TTF:
            return 'createWithTTF("' + self._label_text + '", "'+ g_assetpath + self._font_filename + '", ' + str(self._font_size) + ')'

    def get_description(self, tab):
        return "%s%s('%s')" % ('-' * tab, self.get_class_name(), self._label_text)


class ParticleSystem(Node):
    def __init__(self, data):
        super(ParticleSystem, self).__init__(data)

        component = Node.get_node_component_of_type(self._node_data, 'cc.ParticleSystem')

        self._particle_system_file = Node.get_filepath_from_uuid(component['_file']['__uuid__'])

        # tag it as needed resourse
        g_resources_needed.add(self._particle_system_file)

    def get_class_name(self):
        return 'ParticleSystemQuad'

    def to_cpp_create_params(self):
        return 'create("' + g_assetpath + self._particle_system_file + '")'


class TiledMap(Node):
    def __init__(self, data):
        super(TiledMap, self).__init__(data)

        component = Node.get_node_component_of_type(self._node_data, 'cc.TiledMap')
        self._tmx_file = Node.get_filepath_from_uuid(component['_tmxFile']['__uuid__'])

        # tag it as needed resourse
        g_resources_needed.add(self._tmx_file)

        # for some reason, changing the contentSize breaks the TMX
        del self._properties['setContentSize']

    def get_class_name(self):
        return 'TMXTiledMap'

    def to_cpp_create_params(self):
        return 'create("' + g_assetpath + self._tmx_file + '")'


################################################################################
#
# Built-in UI Nodes
# Button, EditBox, ProgressBar, ScrollView
#
################################################################################
class Button(Node):
    #  Composition:
    #  - Sprite component
    #  - Button component
    #  - Label child
    #    - Label component
    #
    # custom properties
    # "_N$normalSprite": { "__uuid__": }
    # "_N$disabledSprite": { "__uuid__": }
    # "_N$interactable": true,
    # "_N$normalColor": { "__type__": "cc.Color"}
    # "_N$disabledColor": { "__type__": "cc.Color",
    # "transition": 2, (NONE, COLOR, SPRITE)
    # "pressedColor": { "__type__": "cc.Color",
    # "hoverColor": { "__type__": "cc.Color",
    # "duration": 0.1,
    # "pressedSprite": { "__uuid__":
    # "hoverSprite": { "__uuid__":
    TRANSITION_NONE, TRANSITION_COLOR, TRANSITION_SPRITE = range(3)

    def __init__(self, data):
        super(Button, self).__init__(data)

    def parse_properties(self):
        super(Button, self).parse_properties()

        # search for sprite frame name
        spr_component = Node.get_node_component_of_type(self._node_data, 'cc.Sprite')
        but_component = Node.get_node_component_of_type(self._node_data, 'cc.Button')

        self._normalSprite = Node.get_filepath_from_uuid(but_component['_N$normalSprite']['__uuid__'])
        self._properties['ignoreContentAdaptWithSize'] = 'false'

    def get_class_name(self):
        return 'ui::Button'

    def to_cpp_create_params(self):
        return 'create("%s", "", "", ui::Widget::TextureResType::PLIST)' % self._normalSprite

    def to_cpp_add_child(self, child):
        # replaces addChild() with setTitleLabel()
        g_file_cpp.write("    %s->setTitleLabel(%s);\n" % (self._cpp_node_name, child._cpp_node_name))
        g_file_cpp.write("")


class EditBox(Node):
    # custom properties
    # "_N$backgroundImage": { "__uuid__": }
    # "_N$returnType": 0,
    # "_N$inputFlag": 3,
    # "_N$inputMode": 6,
    # "_N$fontSize": 29,
    # "_N$lineHeight": 40,
    # "_N$fontColor": { "__type__": "cc.Color",}
    # "_N$placeholder": "Enter text here...",
    # "_N$placeholderFontSize": 20,
    # "_N$placeholderFontColor": { "__type__": "cc.Color" }
    # "_N$maxLength": 8

    INPUT_MODE = ( 'ui::EditBox::InputMode::ANY',
            'ui::EditBox::InputMode::EMAIL_ADDRESS',
            'ui::EditBox::InputMode::NUMERIC',
            'ui::EditBox::InputMode::PHONE_NUMBER',
            'ui::EditBox::InputMode::URL',
            'ui::EditBox::InputMode::DECIMAL',
            'ui::EditBox::InputMode::SINGLE_LINE'
            )

    INPUT_FLAG = (
            'ui::EditBox::InputFlag::PASSWORD',
            'ui::EditBox::InputFlag::SENSITIVE',
            'ui::EditBox::InputFlag::INITIAL_CAPS_WORD',
            'ui::EditBox::InputFlag::INITIAL_CAPS_SENTENCE',
            'ui::EditBox::InputFlag::INITIAL_CAPS_ALL_CHARACTERS',
            'ui::EditBox::InputFlag::LOWERCASE_ALL_CHARACTERS',
            )

    RETURN_TYPE = (
            'ui::EditBox::KeyboardReturnType::DEFAULT',
            'ui::EditBox::KeyboardReturnType::DONE',
            'ui::EditBox::KeyboardReturnType::SEND',
            'ui::EditBox::KeyboardReturnType::SEARCH',
            'ui::EditBox::KeyboardReturnType::GO',
            )

    def __init__(self, data):
        super(EditBox, self).__init__(data)

    def parse_properties(self):
        super(EditBox, self).parse_properties()

        # search for sprite frame name
        component = Node.get_node_component_of_type(self._node_data, 'cc.EditBox')
        self._backgroundImage = Node.get_filepath_from_uuid(component['_N$backgroundImage']['__uuid__'])
        self._properties['setReturnType'] = EditBox.RETURN_TYPE[component['_N$returnType']]
        self._properties['setInputFlag'] = EditBox.INPUT_FLAG[component['_N$inputFlag']]
        self._properties['setInputMode'] = EditBox.INPUT_MODE[component['_N$inputMode']]
        self.add_property_int('setFontSize', '_N$fontSize', component)
#        self.add_property_int('setLineHeight', '_N$lineHeight', component)
        self.add_property_rgb('setFontColor', '_N$fontColor', component)
        self.add_property_str('setPlaceHolder', '_N$placeholder', component)
        self.add_property_int('setPlaceholderFontSize', '_N$placeholderFontSize', component)
        self.add_property_rgb('setPlaceholderFontColor', '_N$placeholderFontColor', component)
        self.add_property_int('setMaxLength', '_N$maxLength', component)
        self.add_property_str('setText', '_string', component)

    def get_class_name(self):
        return 'ui::EditBox'

    def to_cpp_create_params(self):
        s = self._node_data['_contentSize']
        w = s['width']
        h = s['height']
        return 'create(Size(%d,%d), "%s", ui::Widget::TextureResType::PLIST)' % (w, h, self._backgroundImage)


class ProgressBar(Node):
    # custom properties
    # "_N$barSprite": { "__id__" }
    # "_N$mode": 0,
    # "_N$totalLength": 100,
    # "_N$progress": 0.5,
    # "_N$reverse": false

    def parse_properties(self):
        super(ProgressBar, self).parse_properties()

        # search for sprite frame name
        component = Node.get_node_component_of_type(self._node_data, 'cc.ProgressBar')
        self._properties['setPercent'] = component['_N$progress'] * 100


    def get_class_name(self):
        return 'ui::LoadingBar'

    def to_cpp_create_params(self):
        return 'create()'


class ScrollView(Node):
    # custom properties
    # "horizontal": false,
    # "vertical": true,
    # "inertia": true,
    # "brake": 0.75,
    # "elastic": true,
    # "bounceDuration": 0.23,
    # "scrollEvents": [],
    # "cancelInnerEvents": true,
    # "_N$horizontalScrollBar": null,
    # "_N$verticalScrollBar": { "__id__": 23 }

    # for the sprites used internally
    SIMPLE, SLICED, TILED, FILLED = range(4)

    def get_content_node(self):
        # Node
        #  +--> ScrollBar
        #       +--> Bar
        #  +--> View
        #       +--> Content    <-- this is what we want
        view_node = None
        content_node = None

        # find the "view" node
        for child_idx in self._node_data["_children"]:
            node_idx = child_idx['__id__']
            node = g_json_data[node_idx]

            if node["_name"] == "view":
                view_node = node

        # then find the "content" node
        if view_node is not None:
            for child_idx in view_node["_children"]:
                node_idx = child_idx['__id__']
                node = g_json_data[node_idx]

                if node["_name"] == "content":
                    content_node = node

        if content_node is not None:
            return content_node
        else:
            raise Exception("ContentNode not found")

    def parse_properties(self):
        # Don't call super since it will parse all its children
        # We only care about the "content" child
        # super(ScrollView, self).parse_properties()

        # data from 'node' component
        self.add_property_rgb('setBackGroundImageColor', '_color', self._node_data)

        # data from sprite component
        component_spr = Node.get_node_component_of_type(self._node_data, 'cc.Sprite')
        sprite_frame_uuid = component_spr['_spriteFrame']['__uuid__']
        self._properties['setBackGroundImage'] =  '"%s", ui::Widget::TextureResType::PLIST' % g_sprite_frames[sprite_frame_uuid]['frameName']

        # Sliced ?
        if component_spr['_type'] == ScrollView.SLICED:
            self._properties['setBackGroundImageScale9Enabled'] = "true"
        else:
            self._properties['setBackGroundImageScale9Enabled'] = "false"

        # data from scroll view component
        component_sv = Node.get_node_component_of_type(self._node_data, 'cc.ScrollView')
        if component_sv['horizontal'] and component_sv['vertical']:
            self._properties['setDirection'] = 'ui::ScrollView::Direction::BOTH'
        elif component_sv['horizontal']:
            self._properties['setDirection'] = 'ui::ScrollView::Direction::HORIZONTAL'
        elif component_sv['vertical']:
            self._properties['setDirection'] = 'ui::ScrollView::Direction::VERTICAL'
        else:
            self._properties['setDirection'] = 'ui::ScrollView::Direction::NONE'
        self.add_property_bool('setBounceEnabled', 'elastic', component_sv)

        # content node
        content_node = self.get_content_node()

        # get size from content (which must be >= view.size)
        data = content_node
        self.add_property_size('setInnerContainerSize', "_contentSize", data)
        self._content_size = data['_contentSize']

        # FIXME: Container Node should honor these values, but it seems that ScrollView doesn't
        # take them into account... or perhaps CocosCreator uses a different anchorPoint
        # position is being adjusted in `adjust_child_parameters`
        self._content_ap = content_node['_anchorPoint']

        #self._properties['getInnerContainer()->setAnchorPoint'] = 'Vec2(%g,%g)' % (self._content_ap['x'], self._content_ap['y'])
        self._content_pos = content_node['_position']
        #self._properties['getInnerContainer()->setPosition'] = 'Vec2(%g,%g)' % (self._content_pos['x'], self._content_pos['y'])

        # add its children
        for child_idx in content_node["_children"]:
            self.parse_child(child_idx['__id__'])

    def get_class_name(self):
        return 'ui::ScrollView'

    def to_cpp_create_params(self):
        return 'create()'

    def to_cpp_end(self):
        super(ScrollView, self).to_cpp_end()
        # FIXME: Call setJumpToPercent at the end, because it depens
        # on having the contentSize correct
        # FIXME: uses the anchorPoint for the percent in the bar, but 
        # this migh break if it changes the position of the bar
        # content node
        g_file_cpp.write("    %s->jumpToPercentVertical(%g * 100);\n" % (self._cpp_node_name, (1-self._content_ap['y'])))
        g_file_cpp.write("    %s->jumpToPercentHorizontal(%g * 100);\n" % (self._cpp_node_name, self._content_ap['x']))


    def adjust_child_parameters(self, child):
        # FIXME: adjust child position since innerContainer doesn't honor
        # position and anchorPoit.
        pos = child._properties['setPosition']
        g = re.match('Vec2\(([-+]?[0-9]*\.?[0-9]+), ([-+]?[0-9]*\.?[0-9]+)\)', pos)
        if g is not None:
            x = float(g.group(1))
            y = float(g.group(2))
            child._properties['setPosition'] = "Vec2(%g, %g)" % (x + self._content_size['width'] * self._content_ap['x'],
                    y + self._content_size['height'] * self._content_ap['y'])
        else:
            raise Exception("Could not parse position: %s" % pos)


################################################################################
#
# bootstrap + helper functions
#
################################################################################
def populate_meta_files(path):
    global g_meta_data, g_sprite_frames, g_textures
    global g_sprite_with_atlas, g_sprite_without_atlas
    metas1 = glob.glob(path + '/*.meta')
    metas2 = glob.glob('temp/*/*/*.meta')
    metas = metas1 + metas2
    print(metas)
    for meta_filename in metas:
        with open(meta_filename) as fd:
            basename = os.path.basename(meta_filename)
            j_data = json.load(fd)
            g_meta_data[basename] = j_data

            meta_uuid = j_data['uuid']

            # is this a sprite (.png) file ?
            if 'type' in j_data and (j_data['type'] == 'sprite' or j_data['type'] == 'Texture Packer'):
                # subMetas seems to contain all the sprite frame definitions
                submetas = j_data['subMetas']
                for spriteframename in submetas:
                    # uuid will be used as the key
                    uuid = submetas[spriteframename]['uuid']
                    submetas[spriteframename]['frameName'] = spriteframename

                    # populate g_sprite_frames
                    g_sprite_frames[uuid] = submetas[spriteframename]

                    # populate g_textures. The name is meta_filename - '.meta' (5 chars)
                    if 'rawTextureUuid' in submetas[spriteframename]:
                        texture_uuid = submetas[spriteframename]['rawTextureUuid']
                        g_textures[texture_uuid] = os.path.basename(meta_filename[:-5])
                    else:
                        print('Framename "%s" doesn\'t have rawTextureUuid. Ignoring it...' % submetas[spriteframename]['frameName'])

                    if j_data['type'] == 'sprite':
                        g_sprite_without_atlas[uuid] = submetas[spriteframename]
                    elif j_data['type'] == 'Texture Packer':
                        g_sprite_with_atlas.append(Node.get_filepath_from_uuid(meta_uuid))
                        g_sprite_without_atlas[uuid] = submetas[spriteframename]
                    else:
                        raise Exception("Invalid type: %s" % j_data['type'])


def populate_uuid_file(path):
    global g_uuid
    with open(path + '/../library/uuid-to-mtime.json') as data:
        g_uuid = json.load(data)


def to_cpp_setup():
    header = """
USING_NS_CC;

bool %s_init()
{""" % g_filename

    footer = """
    return true;
}
"""
    g_file_cpp.write(header)
    to_cpp_setup_design_resolution()
    to_cpp_setup_sprite_frames()
    g_file_cpp.write(footer)


def to_cpp_setup_design_resolution():
    design_resolution_exact_fit = """
    auto director = Director::getInstance();
    auto glview = director->getOpenGLView();
    glview->setDesignResolutionSize(%d, %d, ResolutionPolicy::EXACT_FIT);
""" % ( g_design_resolution['width'], g_design_resolution['height'])

    design_resolution = """
    auto director = Director::getInstance();
    auto glview = director->getOpenGLView();
    auto frameSize = glview->getFrameSize();
    glview->setDesignResolutionSize(%s, %s, ResolutionPolicy::NO_BORDER);
"""

    if g_fit_height and g_fit_width:
        g_file_cpp.write(design_resolution_exact_fit)
    elif g_fit_height:
        expanded = design_resolution % (
                "frameSize.width / (frameSize.height / %d)" % g_design_resolution['height'],
                "frameSize.height / (frameSize.height / %d)" % g_design_resolution['height'])
        g_file_cpp.write(expanded)
    elif g_fit_width:
        expanded = design_resolution % (
                "frameSize.width / (frameSize.width / %d)" % g_design_resolution['width'],
                "frameSize.height / (frameSize.width / %d)" % g_design_resolution['width'])
        g_file_cpp.write(expanded)
    else:
        expanded = design_resolution % (
                str(g_design_resolution['width']),
                str(g_design_resolution['height']))
        g_file_cpp.write(expanded)


def to_cpp_setup_sprite_frames():
    g_file_cpp.write('\n    // BEGIN SpriteFrame loading\n')
    g_file_cpp.write('    auto spriteFrameCache = SpriteFrameCache::getInstance();\n')

    g_file_cpp.write('    // Files from .plist\n')
    for k in Set(g_sprite_with_atlas):
        g_file_cpp.write('    // %s processed manually. No need to include it in the assets folder\n' % (g_assetpath + k))
        #g_file_cpp.write('    spriteFrameCache->addSpriteFramesWithFile("%s");\n' % (g_assetpath + k))

    g_file_cpp.write('\n    // Files from .png\n')
    for k in g_sprite_without_atlas:
        sprite_frame = g_sprite_frames[k]
        if 'rawTextureUuid' in sprite_frame:
            texture_filename = Node.get_filepath_from_uuid(sprite_frame['rawTextureUuid'])

            original_frame_name = sprite_frame['frameName']
            sprite_frame_name = original_frame_name.replace('-','_')
            sprite_frame_name = sprite_frame_name.replace('.','_')
            cpp_sprite_frame = '    auto sf_%s = SpriteFrame::create("%s", Rect(%g, %g, %g, %g), %s, Vec2(%g, %g), Size(%g, %g));\n' % (
                    sprite_frame_name,
                    g_assetpath + texture_filename,
                    sprite_frame['trimX'], sprite_frame['trimY'], sprite_frame['width'], sprite_frame['height'],
                    str(sprite_frame['rotated']).lower(),
                    sprite_frame['offsetX'], sprite_frame['offsetY'],
                    sprite_frame['rawWidth'], sprite_frame['rawHeight'])
            g_file_cpp.write(cpp_sprite_frame)

            # does it have a capInsets?
            if sprite_frame['borderTop'] != 0 or sprite_frame['borderBottom'] != 0 or sprite_frame['borderLeft'] != 0 or sprite_frame['borderRight'] != 0:
                x = sprite_frame['borderLeft']
                y = sprite_frame['borderTop']
                w = sprite_frame['width'] - sprite_frame['borderRight'] - x
                h = sprite_frame['height'] - sprite_frame['borderBottom'] - y
                g_file_cpp.write('    sf_%s->setCenterRectInPixels(Rect(%d,%d,%d,%d));\n' % (
                    sprite_frame_name,
                    x, y, w, h
                    ))
            g_file_cpp.write('    spriteFrameCache->addSpriteFrame(sf_%s, "%s");\n' % (
                sprite_frame_name,
                original_frame_name))
        else:
            print("Ignoring '%s'... No rawTextureUuid" % sprite_frame['frameName'])
    g_file_cpp.write('    // END SpriteFrame loading\n')


def create_file(filename):

    if not os.path.exists(os.path.dirname(filename)):
        try:
            os.makedirs(os.path.dirname(filename))
        except OSError as exc: # Guard against race condition
            if exc.errno != errno.EEXIST:
                raise
    return open(filename, "w")


def run(filename, assetpath):
    global g_filename, g_file_cpp, g_file_h, g_assetpath

    globals_init()

    g_assetpath = assetpath
    g_filename = os.path.splitext(os.path.basename(filename))[0]
    cpp_name = "cpp/%s.cpp" % g_filename
    h_name = "cpp/%s.h" % g_filename

    g_file_cpp = create_file(cpp_name)
    g_file_h = create_file(h_name)

    path = os.path.dirname(filename)
    # 1st
    populate_uuid_file(path)
    # 2nd
    populate_meta_files(path)

    global g_json_data
    with open(filename) as data_file:
        g_json_data = json.load(data_file)

    print("total elements: %d" % len(g_json_data))
    for i,obj in enumerate(g_json_data):
        if obj["__type__"] == "cc.SceneAsset":
            scenes = obj["scene"]
            scene_idx = scenes["__id__"]
            scene_obj = Scene(g_json_data[scene_idx])
            scene_obj.parse_properties()
#            scene_obj.print_scene_graph(0)

            # cpp file
            g_file_cpp.write("////// AUTOGENERATED:BEGIN //////\n")
            g_file_cpp.write("////// DO     NOT     EDIT //////\n")
            g_file_cpp.write("\n#include <ui/CocosGUI.h>\n")
            g_file_cpp.write('#include "creator_utils.h"\n')
            to_cpp_setup()
            g_file_cpp.write("Node* %s_create()\n{\n" % g_filename)
            scene_obj.to_cpp(None,0,0)
            g_file_cpp.write("    return scene_0;\n}\n")
            g_file_cpp.write("////// AUTOGENERATED:END//////\n")

            # header file
            header = """
////// AUTOGENERATED:BEGIN //////
////// DO     NOT     EDIT //////
#pragma once

#include <cocos2d.h>

bool %s_init();
cocos2d::Node* %s_create();

////// AUTOGENERATED:END//////
""" % (g_filename, g_filename)
            g_file_h.write(header)


def help():
    print("%s v0.1 - parses Cocos Creator project files\n" % os.path.basename(sys.argv[0]))
    print("Example:\n%s --assetpath creator_assets assets/*.fire" % os.path.basename(sys.argv[0]))
    sys.exit(-1)


if __name__ == "__main__":
    if len(sys.argv) == 1:
        help()

    assetpath = ""
    argv = sys.argv[1:]
    try:
        opts, args = getopt.getopt(argv, "p:", ["assetpath="])
        for opt, arg in opts:
            if opt in ("-p", "--assetpath"):
                assetpath = arg
                if assetpath[-1] != '/':
                    assetpath += '/'

        for f in args:
            run(f, assetpath)
    except getopt.GetoptError, e:
        print(e)

