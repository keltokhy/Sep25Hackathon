#include "drone_pp.h"

#define Env DronePP
#include "../env_binding.h"

static int my_init(Env *env, PyObject *args, PyObject *kwargs) {
    env->num_agents = unpack(kwargs, "num_agents");
    env->max_rings = unpack(kwargs, "max_rings");

    env->penalty_damping = unpack(kwargs, "penalty_damping");
    env->reward_xy_dist = unpack(kwargs, "reward_xy_dist");
    env->reward_hover_dist = unpack(kwargs, "reward_hover_dist");
    env->reward_hover_alt = unpack(kwargs, "reward_hover_alt");
    env->reward_hover = unpack(kwargs, "reward_hover");
    env->reward_maint_hover = unpack(kwargs, "reward_maint_hover");
    env->reward_descent = unpack(kwargs, "reward_descent");
    env->penalty_lost_hover = unpack(kwargs, "penalty_lost_hover");
    env->alignment = unpack(kwargs, "alignment");
    env->min_alignment = unpack(kwargs, "min_alignment");
    env->max_alignment = unpack(kwargs, "max_alignment");

    env->reward_min_dist = unpack(kwargs, "reward_min_dist");
    env->reward_max_dist = unpack(kwargs, "reward_max_dist");
    env->dist_decay = unpack(kwargs, "dist_decay");

    env->w_position = unpack(kwargs, "w_position");
    env->w_velocity = unpack(kwargs, "w_velocity");
    env->w_stability = unpack(kwargs, "w_stability");
    env->w_approach = unpack(kwargs, "w_approach");
    env->w_hover = unpack(kwargs, "w_hover");

    env->pos_const = unpack(kwargs, "pos_const");
    env->pos_penalty = unpack(kwargs, "pos_penalty");

    env->grip_k_min = unpack(kwargs, "grip_k_min");
    env->grip_k_max = unpack(kwargs, "grip_k_max");
    env->grip_k_decay = unpack(kwargs, "grip_k_decay");

    init(env);
    return 0;
}

static int my_log(PyObject *dict, Log *log) {
    assign_to_dict(dict, "perf", log->perf);
    assign_to_dict(dict, "score", log->score);
    assign_to_dict(dict, "rings_passed", log->rings_passed);
    assign_to_dict(dict, "collision_rate", log->collision_rate);
    assign_to_dict(dict, "oob", log->oob);
    assign_to_dict(dict, "episode_return", log->episode_return);
    assign_to_dict(dict, "episode_length", log->episode_length);

    assign_to_dict(dict, "gripping", log->gripping);
    assign_to_dict(dict, "to_pickup", log->to_pickup);
    assign_to_dict(dict, "ho_pickup", log->ho_pickup);
    assign_to_dict(dict, "de_pickup", log->de_pickup);
    assign_to_dict(dict, "to_drop", log->to_drop);
    assign_to_dict(dict, "ho_drop", log->ho_drop);
    assign_to_dict(dict, "dist", log->dist);
    assign_to_dict(dict, "dist100", log->dist100);

    assign_to_dict(dict, "n", log->n);
    return 0;
}
