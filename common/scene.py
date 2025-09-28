#common\scene.py:
import bpy

def clear_animations() -> None:
    actions_to_remove = [action for action in bpy.data.actions if action.users == 0]
    for action in actions_to_remove:
        action.user_clear()
        bpy.data.actions.remove(action)


def frame_timeline(context: bpy.types.Context) -> None:
    for window in context.window_manager.windows:
        screen = window.screen

        for area in screen.areas:
            if area.type in {'DOPESHEET_EDITOR', 'NLA_EDITOR', 'GRAPH_EDITOR'}:
                for region in area.regions:
                    if region.type == 'WINDOW':
                        with context.temp_override(window=window, area=area, region=region):
                            editor_actions = {
                                'DOPESHEET_EDITOR': bpy.ops.action.view_all,
                                'NLA_EDITOR': bpy.ops.nla.view_all,
                                'GRAPH_EDITOR': bpy.ops.graph.view_all
                            }
                            editor_actions[area.type]()


