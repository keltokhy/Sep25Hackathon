#include "drone_pp.h"

#define Env DronePP
#include "../env_binding.h"

static int my_init(Env *env, PyObject *args, PyObject *kwargs) {
    env->num_agents = unpack(kwargs, "num_agents");
    env->max_rings = unpack(kwargs, "max_rings");

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

    env->box_base_density = unpack(kwargs, "box_base_density");
    env->box_k_growth = unpack(kwargs, "box_k_growth");

    env->reward_hover = unpack(kwargs, "reward_hover");
    env->reward_grip = unpack(kwargs, "reward_grip");
    env->reward_deliv = unpack(kwargs, "reward_deliv");

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

    assign_to_dict(dict, "jitter", log->jitter);
    assign_to_dict(dict, "perfect_grip", log->perfect_grip);
    assign_to_dict(dict, "perfect_deliv", log->perfect_deliv);
    assign_to_dict(dict, "perfect_now", log->perfect_now);
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
