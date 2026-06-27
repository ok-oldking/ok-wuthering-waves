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
    elif feature_name == 'e_forte':
        # find_e_forte binarizes the frame; the template must get the same
        # transform or confidences are meaningless (the raw template scored
        # 0.53 against its own annotation source frame, below the 0.6 threshold)
        feature.mat = binarize_for_matching(feature.mat)
