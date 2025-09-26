#common/scene.py
import bpy
import logging
from typing import Optional

# Logger global para o addon
logger = logging.getLogger('dmc_tools')
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('[DMC3] %(levelname)s: %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def log_info(msg: str) -> None:
    logger.info(msg)


def log_warn(msg: str) -> None:
    logger.warning(msg)


def log_error(msg: str) -> None:
    logger.error(msg)


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
                            try:
                                editor_actions[area.type]()
                            except Exception as e:
                                log_warn(f"Could not call view_all for {area.type}: {e}")


def safe_set_mode(context: bpy.types.Context, the_object: bpy.types.Object, mode: str) -> bool:
    if the_object is None:
        log_warn(f"safe_set_mode: target object is None for mode {mode}")
        return False

    try:
        # Garanta que o objeto está ativo na view layer do context
        if context.view_layer.objects.active != the_object:
            # Alguns contextos não permitem trocar o active object diretamente — tente por exceção
            try:
                context.view_layer.objects.active = the_object
            except Exception:
                # fallback: use global context
                bpy.context.view_layer.objects.active = the_object

        # Obtenha o modo atual do contexto de forma robusta
        current_mode = getattr(context, 'mode', None)
        if current_mode is None:
            current_mode = bpy.context.mode

        # Se já estivermos no modo desejado, não faz nada
        if current_mode.upper().startswith(mode.upper()):
            return True

        # Tentar mudar o modo via bpy.ops (usando o contexto corrente)
        try:
            bpy.ops.object.mode_set(mode=mode)
            return True
        except RuntimeError as e:
            # Em alguns casos, precisamos forçar com override
            try:
                # busca uma window/area/region válida para override
                for window in context.window_manager.windows:
                    screen = window.screen
                    for area in screen.areas:
                        if area.type == 'VIEW_3D':
                            for region in area.regions:
                                if region.type == 'WINDOW':
                                    with context.temp_override(window=window, area=area, region=region):
                                        bpy.ops.object.mode_set(mode=mode)
                                        return True
            except Exception:
                log_error(f"Could not set mode {mode} for {getattr(the_object, 'name', '<noname>')}: {e}")
                return False

    except Exception as e:
        log_error(f"Could not set mode {mode} for {getattr(the_object, 'name', '<noname>')}: {e}")
        return False


# Helpers adicionais
def get_armature_object(context: bpy.types.Context, name: str = "Armature_object") -> Optional[bpy.types.Object]:
    return context.scene.objects.get(name)


def ensure_collection(context: bpy.types.Context, name: str) -> bpy.types.Collection:
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        context.scene.collection.children.link(col)
    return col


