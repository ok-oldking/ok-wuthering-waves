from src.task.BaseWWTask import convert_bw, binarize_for_matching, convert_dialog_icon


def process_feature(feature_name, feature):
    if feature_name == 'illusive_realm_exit':
        feature.mat = convert_bw(feature.mat)
    elif feature_name == 'purple_target_distance_icon':
        feature.mat = binarize_for_matching(feature.mat)
    elif feature_name == 'world_earth_icon':
        feature.mat = convert_bw(feature.mat)
    elif feature_name == 'skip_dialog':
        feature.mat = convert_dialog_icon(feature.mat)
    elif feature_name == 'mouse_forte':
        feature.mat = binarize_for_matching(feature.mat)
