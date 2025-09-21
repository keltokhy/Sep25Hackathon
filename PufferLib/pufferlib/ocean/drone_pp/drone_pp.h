// Originally made by Sam Turner and Finlay Sanders, 2025.
// Included in pufferlib under the original project's MIT license.
// https://github.com/stmio/drone

#include <float.h>
#include <math.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#include "raylib.h"
#include "dronelib.h"

#define TASK_IDLE 0
#define TASK_HOVER 1
#define TASK_ORBIT 2
#define TASK_FOLLOW 3
#define TASK_CUBE 4
#define TASK_CONGO 5
#define TASK_FLAG 6
#define TASK_RACE 7
#define TASK_PP2 8
#define TASK_N 9

#define DEBUG 0

char* TASK_NAMES[TASK_N] = {
    "Idle", "Hover", "Orbit", "Follow",
    "Cube", "Congo", "FLAG", "Race", "PP2"
};

#define R (Color){255, 0, 0, 255}
#define W (Color){255, 255, 255, 255}
#define B (Color){0, 0, 255, 255}
Color FLAG_COLORS[64] = {
    B, B, B, B, R, R, R, R,
    B, B, B, B, W, W, W, W,
    B, B, B, B, R, R, R, R,
    B, B, B, B, W, W, W, W,
    R, R, R, R, R, R, R, R,
    W, W, W, W, W, W, W, W,
    R, R, R, R, R, R, R, R,
    W, W, W, W, W, W, W, W
};
#undef R
#undef W
#undef B

typedef struct Client Client;
struct Client {
    Camera3D camera;
    float width;
    float height;

    float camera_distance;
    float camera_azimuth;
    float camera_elevation;
    bool is_dragging;
    Vector2 last_mouse_pos;

    // Trailing path buffer (for rendering only)
    Trail* trails;
};

typedef struct {
    float *observations;
    float *actions;
    float *rewards;
    unsigned char *terminals;

    float dist;

    Log log;
    // Episode-local tick (resets each horizon for rollouts)
    int tick;
    // Monotonic global step counter for curriculum scheduling (never resets)
    unsigned long long global_tick;
    int report_interval;
    bool render;

    int task;
    int num_agents;
    Drone* agents;

    int max_rings;
    Ring* ring_buffer;

    int debug;

    float reward_min_dist;
    float reward_max_dist;
    float dist_decay;
    float reward_dist;

    float w_position;
    float w_velocity;
    float w_stability;
    float w_approach;
    float w_hover;

    float pos_const;
    float pos_penalty;

    float grip_k;
    float grip_k_min;
    float grip_k_max;
    float grip_k_decay;

    float box_base_density;
    float box_k;
    float box_k_min;
    float box_k_max;
    float box_k_growth;

    float reward_hover;
    float reward_grip;
    float reward_deliv;

    Client *client;
} DronePP;

void init(DronePP *env) {
    env->render = false;
    env->box_k = 0.001f;
    env->box_k_min = 0.001f;
    env->box_k_max = 1.0f;
    env->agents = calloc(env->num_agents, sizeof(Drone));
    env->ring_buffer = calloc(env->max_rings, sizeof(Ring));
    env->log = (Log){0};
    env->tick = 0;
    env->global_tick = 0ULL;
}

void add_log(DronePP *env, int idx, bool oob) {
    Drone *agent = &env->agents[idx];
    env->log.score += agent->score;
    env->log.episode_return += agent->episode_return;
    env->log.episode_length += agent->episode_length;
    env->log.collision_rate += agent->collisions / (float)agent->episode_length;
    env->log.perf += agent->score / (float)agent->episode_length;
    if (oob) {
        env->log.oob += 1.0f;
    }
    env->log.n += 1.0f;

    agent->episode_length = 0;
    agent->episode_return = 0.0f;
}

Drone* nearest_drone(DronePP* env, Drone *agent) {
    float min_dist = 999999.0f;
    Drone *nearest = NULL;
    for (int i = 0; i < env->num_agents; i++) {
        Drone *other = &env->agents[i];
        if (other == agent) {
            continue;
        }
        float dx = agent->state.pos.x - other->state.pos.x;
        float dy = agent->state.pos.y - other->state.pos.y;
        float dz = agent->state.pos.z - other->state.pos.z;
        float dist = sqrtf(dx*dx + dy*dy + dz*dz);
        if (dist < min_dist) {
            min_dist = dist;
            nearest = other;
        }
    }
    if (nearest == NULL) {
        int x = 0;

    }
    return nearest;
}

void compute_observations(DronePP *env) {
    int idx = 0;
    for (int i = 0; i < env->num_agents; i++) {
        Drone *agent = &env->agents[i];

        Quat q_inv = quat_inverse(agent->state.quat);
        Vec3 linear_vel_body = quat_rotate(q_inv, agent->state.vel);
        Vec3 drone_up_world = quat_rotate(agent->state.quat, (Vec3){0.0f, 0.0f, 1.0f});

        // TODO: Need abs observations now right? idk
        // 42
        env->observations[idx++] = linear_vel_body.x / agent->params.max_vel;
        env->observations[idx++] = linear_vel_body.y / agent->params.max_vel;
        env->observations[idx++] = linear_vel_body.z / agent->params.max_vel;
        env->observations[idx++] = clampf(agent->state.vel.x, -1.0f, 1.0f);
        env->observations[idx++] = clampf(agent->state.vel.y, -1.0f, 1.0f);
        env->observations[idx++] = clampf(agent->state.vel.z, -1.0f, 1.0f);

        env->observations[idx++] = agent->state.omega.x / agent->params.max_omega;
        env->observations[idx++] = agent->state.omega.y / agent->params.max_omega;
        env->observations[idx++] = agent->state.omega.z / agent->params.max_omega;

        env->observations[idx++] = drone_up_world.x;
        env->observations[idx++] = drone_up_world.y;
        env->observations[idx++] = drone_up_world.z;

        env->observations[idx++] = agent->state.quat.w;
        env->observations[idx++] = agent->state.quat.x;
        env->observations[idx++] = agent->state.quat.y;
        env->observations[idx++] = agent->state.quat.z;

        env->observations[idx++] = agent->state.rpms[0] / agent->params.max_rpm;
        env->observations[idx++] = agent->state.rpms[1] / agent->params.max_rpm;
        env->observations[idx++] = agent->state.rpms[2] / agent->params.max_rpm;
        env->observations[idx++] = agent->state.rpms[3] / agent->params.max_rpm;

        env->observations[idx++] = agent->state.pos.x / GRID_X;
        env->observations[idx++] = agent->state.pos.y / GRID_Y;
        env->observations[idx++] = agent->state.pos.z / GRID_Z;

        // For PP2, guide the policy toward the hidden hover point
        // rather than the box/drop directly to stabilize approach.
        // This preserves the fixed observation size while aligning
        // guidance with the phase logic (hover -> descend -> grip).
        Vec3 obs_tgt = agent->target_pos;
        if (env->task == TASK_PP2) {
            obs_tgt = agent->hidden_pos;
        }
        float dx = obs_tgt.x - agent->state.pos.x;
        float dy = obs_tgt.y - agent->state.pos.y;
        float dz = obs_tgt.z - agent->state.pos.z;
        env->observations[idx++] = clampf(dx, -1.0f, 1.0f);
        env->observations[idx++] = clampf(dy, -1.0f, 1.0f);
        env->observations[idx++] = clampf(dz, -1.0f, 1.0f);
        env->observations[idx++] = dx / GRID_X;
        env->observations[idx++] = dy / GRID_Y;
        env->observations[idx++] = dz / GRID_Z;

        env->observations[idx++] = agent->last_collision_reward;
        env->observations[idx++] = agent->last_target_reward;
        env->observations[idx++] = agent->last_abs_reward;
        // todo add other rewards like vel stab approach hover etc

        // Multiagent obs
        Drone* nearest = nearest_drone(env, agent);
        if (env->num_agents > 1) {
            env->observations[idx++] = clampf(nearest->state.pos.x - agent->state.pos.x, -1.0f, 1.0f);
            env->observations[idx++] = clampf(nearest->state.pos.y - agent->state.pos.y, -1.0f, 1.0f);
            env->observations[idx++] = clampf(nearest->state.pos.z - agent->state.pos.z, -1.0f, 1.0f);
        } else {
            env->observations[idx++] = 0.0f;
            env->observations[idx++] = 0.0f;
            env->observations[idx++] = 0.0f;
        }

        // Ring obs
        if (env->task == TASK_RACE) {
            Ring ring = env->ring_buffer[agent->ring_idx];
            Vec3 to_ring = quat_rotate(q_inv, sub3(ring.pos, agent->state.pos));
            Vec3 ring_norm = quat_rotate(q_inv, ring.normal);
            env->observations[idx++] = to_ring.x / GRID_X;
            env->observations[idx++] = to_ring.y / GRID_Y;
            env->observations[idx++] = to_ring.z / GRID_Z;
            env->observations[idx++] = ring_norm.x;
            env->observations[idx++] = ring_norm.y;
            env->observations[idx++] = ring_norm.z;
            env->observations[idx++] = 0.0f; // TASK_PP2
        } else if (env->task == TASK_PP2) {
            Vec3 to_box = quat_rotate(q_inv, sub3(agent->box_pos, agent->state.pos));
            Vec3 to_drop = quat_rotate(q_inv, sub3(agent->drop_pos, agent->state.pos));
            env->observations[idx++] = to_box.x / GRID_X;
            env->observations[idx++] = to_box.y / GRID_Y;
            env->observations[idx++] = to_box.z / GRID_Z;
            env->observations[idx++] = to_drop.x / GRID_X;
            env->observations[idx++] = to_drop.y / GRID_Y;
            env->observations[idx++] = to_drop.z / GRID_Z;
            env->observations[idx++] = 1.0f; // TASK_PP2
         } else {
            env->observations[idx++] = 0.0f;
            env->observations[idx++] = 0.0f;
            env->observations[idx++] = 0.0f;
            env->observations[idx++] = 0.0f;
            env->observations[idx++] = 0.0f;
            env->observations[idx++] = 0.0f;
            env->observations[idx++] = 0.0f; // TASK_PP2
        }
    }
}

void move_target(DronePP* env, Drone *agent) {
    agent->target_pos.x += agent->target_vel.x;
    agent->target_pos.y += agent->target_vel.y;
    agent->target_pos.z += agent->target_vel.z;
    if (agent->target_pos.x < -GRID_X || agent->target_pos.x > GRID_X) {
        agent->target_vel.x = -agent->target_vel.x;
    }
    if (agent->target_pos.y < -GRID_Y || agent->target_pos.y > GRID_Y) {
        agent->target_vel.y = -agent->target_vel.y;
    }
    if (agent->target_pos.z < -GRID_Z || agent->target_pos.z > GRID_Z) {
        agent->target_vel.z = -agent->target_vel.z;
    }
    agent->hidden_pos = agent->target_pos;
    agent->hidden_vel = agent->target_vel;
}

void set_target_idle(DronePP* env, int idx) {
    Drone *agent = &env->agents[idx];
    agent->target_pos = (Vec3){rndf(-MARGIN_X, MARGIN_X), rndf(-MARGIN_Y, MARGIN_Y), rndf(-MARGIN_Z, MARGIN_Z)};
    agent->target_vel = (Vec3){rndf(-V_TARGET, V_TARGET), rndf(-V_TARGET, V_TARGET), rndf(-V_TARGET, V_TARGET)};
}

void set_target_hover(DronePP* env, int idx) {
    Drone *agent = &env->agents[idx];
    agent->target_pos = agent->state.pos;
    agent->target_vel = (Vec3){0.0f, 0.0f, 0.0f};
}

void set_target_orbit(DronePP* env, int idx) {
    // Fibbonacci sphere algorithm
    float R = 8.0f;
    float phi = PI * (sqrt(5.0f) - 1.0f);
    float y = 1.0f - 2*((float)idx / (float)env->num_agents);
    float radius = sqrtf(1.0f - y*y);

    float theta = phi * idx;

    float x = cos(theta) * radius;
    float z = sin(theta) * radius;

    Drone *agent = &env->agents[idx];
    agent->target_pos = (Vec3){R*x, R*z, R*y}; // convert to z up 
    agent->target_vel = (Vec3){0.0f, 0.0f, 0.0f};
}

void set_target_follow(DronePP* env, int idx) {
    Drone* agent = &env->agents[idx];
    if (idx == 0) {
        set_target_idle(env, idx);
    } else {
        agent->target_pos = env->agents[0].target_pos;
        agent->target_vel = env->agents[0].target_vel;
    }
}

void set_target_cube(DronePP* env, int idx) {
    Drone* agent = &env->agents[idx];
    float z = idx / 16;
    idx = idx % 16;
    float x = (float)(idx % 4);
    float y = (float)(idx / 4);
    agent->target_pos = (Vec3){4*x - 6, 4*y - 6, 4*z - 6};
    agent->target_vel = (Vec3){0.0f, 0.0f, 0.0f};
}

void set_target_congo(DronePP* env, int idx) {
    if (idx == 0) {
        set_target_idle(env, idx);
        return;
    }
    Drone* follow = &env->agents[idx - 1];
    Drone* lead = &env->agents[idx];
    lead->target_pos = follow->target_pos;
    lead->target_vel = follow->target_vel;

    // TODO: Slow hack
    for (int i = 0; i < 40; i++) {
        move_target(env, lead);
    }
}

void set_target_flag(DronePP* env, int idx) {
    Drone* agent = &env->agents[idx];
    float x = (float)(idx % 8);
    float y = (float)(idx / 8);
    x = 2.0f*x - 7;
    y = 5 - 1.5f*y;
    agent->target_pos = (Vec3){0.0f, x, y};
    agent->target_vel = (Vec3){0.0f, 0.0f, 0.0f};
}

void set_target_race(DronePP* env, int idx) {
    Drone* agent = &env->agents[idx];
    agent->target_pos = env->ring_buffer[agent->ring_idx].pos;
    agent->target_vel = (Vec3){0.0f, 0.0f, 0.0f};
}

void set_target_pp2(DronePP* env, int idx) {
    Drone* agent = &env->agents[idx];
    if (!agent->gripping) {
        agent->target_pos = (Vec3){agent->box_pos.x, agent->box_pos.y, agent->box_pos.z};
    } else {
        agent->target_pos = (Vec3){agent->drop_pos.x, agent->drop_pos.y, agent->drop_pos.z};
    }
    agent->target_vel = (Vec3){0.0f, 0.0f, 0.0f};
}

void set_target(DronePP* env, int idx) {
    if (env->task == TASK_IDLE) {
        set_target_idle(env, idx);
    } else if (env->task == TASK_HOVER) {
        set_target_hover(env, idx);
    } else if (env->task == TASK_ORBIT) {
        set_target_orbit(env, idx);
    } else if (env->task == TASK_FOLLOW) {
        set_target_follow(env, idx);
    } else if (env->task == TASK_CUBE) {
        set_target_cube(env, idx);
    } else if (env->task == TASK_CONGO) {
        set_target_congo(env, idx);
    } else if (env->task == TASK_FLAG) {
        set_target_flag(env, idx);
    } else if (env->task == TASK_RACE) {
        set_target_race(env, idx);
    } else if (env->task == TASK_PP2) {
        set_target_pp2(env, idx);
    }
}

float compute_reward(DronePP* env, Drone *agent, bool collision) {
    if (DEBUG > 0) printf("  Compute Reward\n");
    Vec3 tgt = agent->target_pos;
    if (env->task == TASK_PP2) tgt = agent->hidden_pos;

    Vec3 pos_error = {agent->state.pos.x - tgt.x, agent->state.pos.y - tgt.y, agent->state.pos.z - tgt.z};
    float dist = sqrtf(pos_error.x * pos_error.x + pos_error.y * pos_error.y + pos_error.z * pos_error.z) + 0.00000001;

    Vec3 vel_error = {agent->state.vel.x, agent->state.vel.y, agent->state.vel.z - agent->hidden_vel.z};
    float vel_magnitude = sqrtf(vel_error.x * vel_error.x + vel_error.y * vel_error.y + vel_error.z * vel_error.z);

    float angular_vel_magnitude = sqrtf(agent->state.omega.x * agent->state.omega.x +
                                      agent->state.omega.y * agent->state.omega.y +
                                      agent->state.omega.z * agent->state.omega.z);

    float proximity_factor = clampf(1.0f - dist / env->reward_dist, 0.0f, 1.0f);

    env->reward_dist = clampf(env->tick * -env->dist_decay + env->reward_max_dist, env->reward_min_dist, 100.0f);

    float position_reward = clampf(expf(-dist / (env->reward_dist * env->pos_const)), -env->pos_penalty, 1.0f);

    // Gentle velocity penalty with distance-based scaling.
    // Near target (< ~5m): full penalty to encourage careful approach
    // Far from target: reduced penalty (floor at 10% strength) to allow efficient travel
    float distance_factor = fminf(1.0f, fmaxf(0.1f, 1.0f - (dist - 5.0f) / 20.0f));
    float base_penalty = clampf((2.0f * expf(-(vel_magnitude - 0.05f) * 10.0f) - 1.0f), -1.0f, 1.0f);
    float velocity_penalty = base_penalty * distance_factor;
    if (DEBUG > 0) printf("    velocity_penalty = %.3f\n", velocity_penalty);

    float stability_reward = -angular_vel_magnitude / agent->params.max_omega;

    Vec3 to_target_unit = {0, 0, 0};
    if (dist > 0.001f) {
        to_target_unit.x = -pos_error.x / dist;
        to_target_unit.y = -pos_error.y / dist;
        to_target_unit.z = -pos_error.z / dist;
    }
    float approach_dot = to_target_unit.x * agent->state.vel.x +
                        to_target_unit.y * agent->state.vel.y +
                        to_target_unit.z * agent->state.vel.z;

    float approach_weight = clampf(dist / env->reward_dist, 0.0f, 1.0f); // todo
    float approach_reward = approach_weight * clampf(approach_dot / agent->params.max_vel, -0.5f, 0.5f);

    float hover_bonus = 0.0f; // todo add a K
    if (dist < env->reward_dist * 0.2f && vel_magnitude < 0.2f && agent->state.vel.z < 0.0f) {
        hover_bonus = env->reward_hover;
    }

    float collision_penalty = 0.0f;
    if (collision && env->num_agents > 1) {
        Drone *nearest = nearest_drone(env, agent);
        float dx = agent->state.pos.x - nearest->state.pos.x;
        float dy = agent->state.pos.y - nearest->state.pos.y;
        float dz = agent->state.pos.z - nearest->state.pos.z;
        float min_dist = sqrtf(dx*dx + dy*dy + dz*dz);
        if (min_dist < 1.0f) {
            collision_penalty = -1.0f;
            agent->collisions += 1.0f;
        }
    }

    float total_reward = env->w_position * position_reward +
                        env->w_velocity * velocity_penalty +
                        env->w_stability * stability_reward +
                        env->w_approach * approach_reward +
                        hover_bonus +
                        collision_penalty;

    // Mild boundary proximity penalty (XY only) to reduce OOB without adding
    // soft walls or centralizing forces. Penalize only when an agent roams
    // outside the inner 80% of the arena, scaling up to the hard boundary.
    float frac_x = fabsf(agent->state.pos.x) / GRID_X;
    float frac_y = fabsf(agent->state.pos.y) / GRID_Y;
    float over_x = fmaxf(0.0f, frac_x - 0.80f) / 0.20f;
    float over_y = fmaxf(0.0f, frac_y - 0.80f) / 0.20f;
    float boundary_prox = fminf(1.0f, fmaxf(over_x, over_y));
    // Small fixed weight so no config change needed
    total_reward -= 0.15f * boundary_prox;

    total_reward = clampf(total_reward, -1.0f, 1.0f);

    float delta_reward = total_reward - agent->last_abs_reward;

    agent->last_collision_reward = collision_penalty;
    agent->last_target_reward = position_reward;
    agent->last_abs_reward = total_reward;
    agent->episode_length++;
    agent->score += total_reward;
    env->dist = dist * dist;
    agent->jitter = 10.0f - (dist + vel_magnitude + angular_vel_magnitude);

    return delta_reward;
}

void reset_pp2(DronePP* env, Drone *agent, int idx) {
    // Keep box/drop spawns away from hard XY boundaries and slightly off the floor
    // to reduce early OOB and floor strikes while preserving pickup geometry.
    // Increase margin further to centralize starts while OOB remains high.
    // Hypothesis: spawning farther from hard walls reduces immediate fly‑offs
    // and gives policies more on‑policy experience near the pickup zone.
    float edge_margin = 20.0f;
    agent->box_pos = (Vec3){
        rndf(-MARGIN_X + edge_margin, MARGIN_X - edge_margin),
        rndf(-MARGIN_Y + edge_margin, MARGIN_Y - edge_margin),
        -GRID_Z + 1.5f
    };
    agent->drop_pos = (Vec3){
        rndf(-MARGIN_X + edge_margin, MARGIN_X - edge_margin),
        rndf(-MARGIN_Y + edge_margin, MARGIN_Y - edge_margin),
        -GRID_Z + 1.5f
    };
    agent->gripping = false;
    agent->delivered = false;
    agent->grip_height = 0.0f;
    agent->approaching_pickup = false;
    agent->hovering_pickup = false;
    agent->descent_pickup = false;
    agent->approaching_drop = false;
    agent->hovering_drop = false;
    agent->descent_drop = false;
    agent->hover_timer = 0.0f;
    agent->target_pos = agent->box_pos;
    agent->hidden_pos = agent->target_pos;
    agent->hidden_pos.z += 1.0f;
    agent->hidden_vel = (Vec3){0.0f, 0.0f, 0.0f};

    float drone_capacity = agent->params.arm_len * 4.0f;
    agent->box_size = rndf(0.05f, fmaxf(drone_capacity, 0.1f));

    float box_volume = agent->box_size * agent->box_size * agent->box_size;
    agent->box_base_mass = env->box_base_density * box_volume * rndf(0.5f, 2.0f);
    agent->box_mass = env->box_k * agent->box_base_mass;

    agent->base_mass = agent->params.mass;
    agent->base_ixx = agent->params.ixx;
    agent->base_iyy = agent->params.iyy;
    agent->base_izz = agent->params.izz;
    agent->base_k_drag = agent->params.k_drag;
    agent->base_b_drag = agent->params.b_drag;
}

void reset_agent(DronePP* env, Drone *agent, int idx) {
    agent->episode_return = 0.0f;
    agent->episode_length = 0;
    agent->collisions = 0.0f;
    agent->score = 0.0f;
    agent->ring_idx = 0;
    agent->perfect_grip = false;
    agent->perfect_deliveries = 0.0f;
    agent->perfect_deliv = false;
    agent->perfect_now = false;
    agent->has_delivered = false;
    agent->jitter = 100.0f;
    agent->box_physics_on = false;

    //float size = 0.2f;
    //init_drone(agent, size, 0.0f);
    float size = rndf(0.3f, 1.0);
    init_drone(agent, size, 0.25f);
    agent->color = FLAG_COLORS[idx];
    agent->color = (Color){255, 0, 0, 255};

    if (env->task == TASK_PP2) {
        // Spawn drones away from hard XY boundaries and a bit higher off the floor
        // for stability. Keep centralization but avoid overcrowding on the floor.
        // Nudge margin up while OOB is dominant in recent runs.
        float edge_margin = 20.0f;
        float z_min = -GRID_Z + 3.5f;
        float z_max = GRID_Z - 1.0f;
        agent->state.pos = (Vec3){
            rndf(-MARGIN_X + edge_margin, MARGIN_X - edge_margin),
            rndf(-MARGIN_Y + edge_margin, MARGIN_Y - edge_margin),
            rndf(z_min, z_max)
        };
    } else {
        agent->state.pos = (Vec3){
            rndf(-MARGIN_X, MARGIN_X),
            rndf(-MARGIN_Y, MARGIN_Y),
            rndf(-MARGIN_Z, MARGIN_Z)
        };
    }
    agent->prev_pos = agent->state.pos;
    agent->spawn_pos = agent->state.pos;

    if (env->task == TASK_PP2) {
        reset_pp2(env, agent, idx);
    }

    compute_reward(env, agent, env->task != TASK_RACE);
}

void random_bump(Drone* agent) {
    agent->state.vel.x += rndf(-0.1f, 0.1f);
    agent->state.vel.y += rndf(-0.1f, 0.1f);
    agent->state.vel.z += rndf(0.05f, 0.3f);
    agent->state.omega.x += rndf(-0.5f, 0.5f);
    agent->state.omega.y += rndf(-0.5f, 0.5f);
    agent->state.omega.z += rndf(-0.5f, 0.5f);

}

void update_gripping_physics(Drone* agent) {
    if (agent->gripping) {
        agent->params.mass = agent->base_mass + agent->box_mass * rndf(0.9f, 1.1f);

        float grip_dist = agent->box_size * 0.5f;
        float added_inertia = agent->box_mass * grip_dist * grip_dist * rndf(0.8f, 1.2f);
        agent->params.ixx = agent->base_ixx + added_inertia;
        agent->params.iyy = agent->base_iyy + added_inertia;
        agent->params.izz = agent->base_izz + added_inertia * 0.5f;

        float drag_multiplier = 1.0f + (agent->box_size / agent->params.arm_len) * rndf(0.5f, 1.0f);
        agent->params.k_drag = agent->base_k_drag * drag_multiplier;
        agent->params.b_drag = agent->base_b_drag * drag_multiplier;
        agent->box_physics_on = true;
    } else {
        agent->params.mass = agent->base_mass;
        agent->params.ixx = agent->base_ixx;
        agent->params.iyy = agent->base_iyy;
        agent->params.izz = agent->base_izz;
        agent->params.k_drag = agent->base_k_drag;
        agent->params.b_drag = agent->base_b_drag;
    }
}

void c_reset(DronePP *env) {
    env->tick = 0;
    //env->task = rand() % (TASK_N - 1);
    
    if (rand() % 4) {
        env->task = TASK_PP2; //CHOOSE TASK
    } else {
        env->task = rand() % (TASK_N - 1);
    }
    env->task = TASK_PP2;

    for (int i = 0; i < env->num_agents; i++) {
        Drone *agent = &env->agents[i];
        reset_agent(env, agent, i);
        set_target(env, i);
    }

    for (int i = 0; i < env->max_rings; i++) {
        Ring *ring = &env->ring_buffer[i];
        *ring = (Ring){0};
    }
    if (env->task == TASK_RACE) {
        float ring_radius = 2.0f;
        reset_rings(env->ring_buffer, env->max_rings, ring_radius);

        // start drone at least MARGIN away from the first ring
        for (int i = 0; i < env->num_agents; i++) {
            Drone *drone = &env->agents[i];
            do {
                drone->state.pos = (Vec3){
                    rndf(-MARGIN_X, MARGIN_X), 
                    rndf(-MARGIN_Y, MARGIN_Y), 
                    rndf(-MARGIN_Z, MARGIN_Z)
                };
            } while (norm3(sub3(drone->state.pos, env->ring_buffer[0].pos)) < 2.0f*ring_radius);
        }
    }
 
    compute_observations(env);
}

void c_step(DronePP *env) {
    env->tick = (env->tick + 1) % HORIZON;
    env->global_tick++;
    //env->log.dist = 0.0f;
    //env->log.dist100 = 0.0f;
    for (int i = 0; i < env->num_agents; i++) {
        Drone *agent = &env->agents[i];
        env->rewards[i] = 0;
        env->terminals[i] = 0;
        agent->perfect_now = false;

        float* atn = &env->actions[4*i];
            // Gentle early action scaling to curb saturation and OOB.
            // Slow the ramp further: 0.5 → 1.0 over ~800k global steps.
            // Rationale: OOB remains ~0.95; extending the low-gain window
            // helps stabilize basic hover/approach without physics hacks.
            float act_scale = 0.5f + 0.5f * fminf(1.0f, (float)env->global_tick / 800000.0f);
            atn[0] *= act_scale;
            atn[1] *= act_scale;
            atn[2] *= act_scale;
            atn[3] *= act_scale;
        move_drone(agent, atn);

        bool out_of_bounds = agent->state.pos.x < -GRID_X || agent->state.pos.x > GRID_X ||
                             agent->state.pos.y < -GRID_Y || agent->state.pos.y > GRID_Y ||
                             agent->state.pos.z < -GRID_Z || agent->state.pos.z > GRID_Z;

        if (!(env->task == TASK_PP2)) move_target(env, agent);

        float reward = 0.0f;
        if (env->task == TASK_RACE) {
            Ring *ring = &env->ring_buffer[agent->ring_idx];
            reward = compute_reward(env, agent, true);
            float passed_ring = check_ring(agent, ring);
            if (passed_ring > 0) {
                agent->ring_idx = (agent->ring_idx + 1) % env->max_rings;
                env->log.rings_passed += 1.0f;
                set_target(env, i);
                compute_reward(env, agent, true);
            }
            reward += passed_ring;
        // =========================================================================================================================================
        // =========================================================================================================================================
        // =========================================================================================================================================
        } else if (env->task == TASK_PP2) {
            if (DEBUG > 0) printf("\n\n===%d===\n", env->tick);
            agent->hidden_pos.x += agent->hidden_vel.x * DT;
            agent->hidden_pos.y += agent->hidden_vel.y * DT;
            agent->hidden_pos.z += agent->hidden_vel.z * DT;
            if (agent->hidden_pos.z < agent->target_pos.z) {
                agent->hidden_pos.z = agent->target_pos.z;
                agent->hidden_vel.z = 0.0f;
            }
            agent->approaching_pickup = true;
            float speed = norm3(agent->state.vel);
            // Use global_tick to schedule curriculum so k evolves smoothly across training.
            // Clamp the effective decay to avoid collapsing difficulty too quickly when
            // configs set an aggressive value (e.g., 0.02). Target ~200k global steps
            // to go from k_max to k_min: max_decay = (k_max - k_min) / 200_000.
            float sched_t = (float)env->global_tick;
            // Slow down curriculum: keep k high for much longer so
            // agents can reliably learn hover/descend/grip before
            // gates tighten. Previously ~200k steps; now ~50M.
            float max_decay = (env->grip_k_max - env->grip_k_min) / 50000000.0f;
            float decay = fminf(env->grip_k_decay, max_decay);
            env->grip_k = clampf(sched_t * -decay + env->grip_k_max, env->grip_k_min, 100.0f);
            env->box_k = clampf(sched_t * env->box_k_growth + env->box_k_min, env->box_k_min, env->box_k_max);
            agent->box_mass = env->box_k * agent->box_base_mass;
            float k = env->grip_k;
            if (DEBUG > 0) printf("  PP2\n");
            if (DEBUG > 0) printf("    K = %.3f\n", k);
            if (DEBUG > 0) printf("    Hidden = %.3f %.3f %.3f\n", agent->hidden_pos.x, agent->hidden_pos.y, agent->hidden_pos.z);
            if (DEBUG > 0) printf("    HiddenV = %.3f %.3f %.3f\n", agent->hidden_vel.x, agent->hidden_vel.y, agent->hidden_vel.z);
            if (DEBUG > 0) printf("    speed = %.3f\n", speed);
            if (!agent->gripping) {
                float dist_to_hidden = sqrtf(powf(agent->state.pos.x - agent->hidden_pos.x, 2) +
                                            powf(agent->state.pos.y - agent->hidden_pos.y, 2) +
                                            powf(agent->state.pos.z - agent->hidden_pos.z, 2));
                float xy_dist_to_box = sqrtf(powf(agent->state.pos.x - agent->box_pos.x, 2) +
                                            powf(agent->state.pos.y - agent->box_pos.y, 2));
                float z_dist_above_box = agent->state.pos.z - agent->box_pos.z;

                // Phase 1 Box Hover
                if (!agent->hovering_pickup) {
                    if (DEBUG > 0) printf("  Phase1\n");
                    if (DEBUG > 0) printf("    dist_to_hidden = %.3f\n", dist_to_hidden);
                    if (DEBUG > 0) printf("    xy_dist_to_box = %.3f\n", xy_dist_to_box);
                    if (DEBUG > 0) printf("    z_dist_above_box = %.3f\n", z_dist_above_box);
                    // Relaxed hover gate: allow a slightly larger positional envelope
                    // and speed tolerance to let early policies register hovering
                    // before learning precise stabilization. This should raise
                    // ho_pickup without adding physics hacks.
                    const float hover_dist_tol = 0.8f;  // was 0.4f
                    const float hover_speed_tol = 0.6f; // was 0.4f
                    if (dist_to_hidden < hover_dist_tol && speed < hover_speed_tol) {
                        agent->hovering_pickup = true;
                        agent->color = (Color){255, 255, 255, 255}; // White
                    } else {
                        if (!agent->has_delivered) {
                            agent->color = (Color){255, 100, 100, 255}; // Light Red
                        }
                    }
                }

                // Phase 2 Box Descent
                else {
                    agent->descent_pickup = true;
                    // Slow descent for stability during pickup
                    agent->hidden_vel = (Vec3){0.0f, 0.0f, -0.05f};
                    if (DEBUG > 0) printf("  GRIP\n");
                    if (DEBUG > 0) printf("    xy_dist_to_box = %.3f\n", xy_dist_to_box);
                    if (DEBUG > 0) printf("    z_dist_above_box = %.3f\n", z_dist_above_box);
                    if (DEBUG > 0) printf("    speed = %.3f\n", speed);
                    if (DEBUG > 0) printf("    agent->state.vel.z = %.3f\n", agent->state.vel.z);
                    // Near-miss diagnostics: count an attempted grip when the
                    // agent is close and descending but misses strict gates.
                    // This is logging-only; no reward change.
                    // Slightly widen near-miss window to better reflect genuine attempts
                    // seen in recent runs without affecting rewards.
                    float near_xy_tol = fmaxf(0.40f, k * 0.30f);
                    float near_z_tol  = fmaxf(0.35f, k * 0.30f);
                    bool near_xy = (xy_dist_to_box < near_xy_tol);
                    bool near_z  = (z_dist_above_box < near_z_tol && z_dist_above_box > -0.10f);
                    bool near_v  = (speed < fmaxf(0.6f, k * 0.6f));
                    bool desc_z  = (agent->state.vel.z <= 0.0f);
                    if (near_xy && near_z && near_v && desc_z) {
                        env->log.attempt_grip += 1.0f;
                    }

                    // Relax pickup grip gate with minimum floors so learning persists
                    // even once k decays to ~1.0. This should convert frequent
                    // hover/descend events into occasional grips to bootstrap carry.
                    // Slightly relax pickup grip gate floors to convert
                    // frequent near-misses into occasional grips while k≈1.
                    // Rationale: logs show ho/de_pickup high and attempt_grip>0
                    // but perfect_grip=0. Widen XY/Z and speed/vertical-velocity
                    // tolerances modestly to bootstrap carry without physics hacks.
                    float grip_xy_tol = fmaxf(0.40f, k * 0.25f);
                    float grip_z_tol  = fmaxf(0.35f, k * 0.25f);
                    float grip_v_tol  = fmaxf(0.50f, k * 0.30f);
                    float grip_vz_tol = fmaxf(0.18f, k * 0.10f);
                    if (
                        xy_dist_to_box < grip_xy_tol &&
                        z_dist_above_box < grip_z_tol && z_dist_above_box > -0.02f &&
                        speed < grip_v_tol &&
                        agent->state.vel.z > -grip_vz_tol && agent->state.vel.z <= 0.05f
                    ) {
                        if (k < 1.01 && env->box_k > 0.99f) {
                            agent->perfect_grip = true;
                            agent->color = (Color){100, 100, 255, 255}; // Light Blue
                        }
                        agent->gripping = true;
                        // Apply gripped mass/drag immediately so carry dynamics
                        // are reflected during the transport phase, not only
                        // when ascending toward drop.
                        update_gripping_physics(agent);
                        reward += env->reward_grip;
                        random_bump(agent);
                    } else if (dist_to_hidden > 0.4f || speed > 0.4f) {
                        agent->color = (Color){255, 100, 100, 255}; // Light Red
                    }
                }
            } else {

                // Phase 3 Drop Hover
                agent->box_pos = agent->state.pos;
                agent->box_pos.z -= 0.5f;
                agent->target_pos = agent->drop_pos;
                agent->approaching_drop = true;
                float xy_dist_to_drop = sqrtf(powf(agent->state.pos.x - agent->drop_pos.x, 2) +
                                            powf(agent->state.pos.y - agent->drop_pos.y, 2));
                float z_dist_above_drop = agent->state.pos.z - agent->drop_pos.z;

                if (!agent->box_physics_on && agent->state.vel.z > 0.3f) {
                    update_gripping_physics(agent);
                }

                if (!agent->hovering_drop) {
                    agent->target_pos = (Vec3){agent->drop_pos.x, agent->drop_pos.y, agent->drop_pos.z + 0.4f};
                    agent->hidden_pos = (Vec3){agent->drop_pos.x, agent->drop_pos.y, agent->drop_pos.z + 1.0f};
                    agent->hidden_vel = (Vec3){0.0f, 0.0f, 0.0f};
                    if (xy_dist_to_drop < k * 0.4f && z_dist_above_drop > 0.7f && z_dist_above_drop < 1.3f) {
                        agent->hovering_drop = true;
                        reward += 0.25;
                        agent->color = (Color){0, 0, 255, 255}; // Blue
                    }
                }

                // Phase 4 Drop Descent
                else {
                    agent->target_pos = agent->drop_pos;
                    agent->hidden_pos.x = agent->drop_pos.x;
                    agent->hidden_pos.y = agent->drop_pos.y;
                    // Slow descent for stability during drop
                    agent->hidden_vel = (Vec3){0.0f, 0.0f, -0.05f};
                    // Near-miss diagnostics for drops
                    float near_drop_xy_tol = fmaxf(0.40f, k * 0.30f);
                    float near_drop_z_tol  = fmaxf(0.30f, k * 0.30f);
                    if (xy_dist_to_drop < near_drop_xy_tol && fabsf(z_dist_above_drop) < near_drop_z_tol) {
                        env->log.attempt_drop += 1.0f;
                    }
                    if (xy_dist_to_drop < k * 0.2f && z_dist_above_drop < k * 0.2f) {
                        agent->hovering_pickup = false;
                        agent->gripping = false;
                        update_gripping_physics(agent);
                        agent->box_physics_on = false;
                        agent->hovering_drop = false;
                        reward += env->reward_deliv;
                        agent->delivered = true;
                        agent->has_delivered = true;
                        if (k < 1.01f && agent->perfect_grip  && env->box_k > 0.99f) {
                            agent->perfect_deliv = true;
                            agent->perfect_deliveries += 1.0f;
                            agent->perfect_now = true;
                            agent->color = (Color){0, 255, 0, 255}; // Green
                        }
                        reset_pp2(env, agent, i);
                    }
                }
            }

            reward += compute_reward(env, agent, true);

            for (int i = 0; i < env->num_agents; i++) {
                Drone *a = &env->agents[i];
                env->log.dist += env->dist;
                env->log.dist100 += 100 - env->dist;
                env->log.jitter += a->jitter;
                if (a->approaching_pickup) env->log.to_pickup += 1.0f;
                if (a->hovering_pickup) env->log.ho_pickup += 1.0f;
                if (a->descent_pickup) env->log.de_pickup += 1.0f;
                if (a->gripping) env->log.gripping += 1.0f;
                if (a->delivered) env->log.delivered += 1.0f;
                if (a->perfect_grip && env->grip_k < 1.01f) env->log.perfect_grip += 1.0f;
                if (a->perfect_deliv && env->grip_k < 1.01f && a->perfect_grip) env->log.perfect_deliv += agent->perfect_deliveries;
                if (a->perfect_deliv && env->grip_k < 1.01f && a->perfect_grip && a->perfect_now && env->box_k > 0.99f) env->log.perfect_now += 1.0f;
                if (a->approaching_drop) env->log.to_drop += 1.0f;
                if (a->hovering_drop) env->log.ho_drop += 1.0f;
            }
        // =========================================================================================================================================
        // =========================================================================================================================================
        // =========================================================================================================================================
        } else {
            // Delta reward
            reward = compute_reward(env, agent, true);
        }

        env->rewards[i] += reward;
        agent->episode_return += reward;

        float min_z = -GRID_Z + 1.0f;
        if (agent->gripping) {
            min_z += 0.3f;
        }

        if (out_of_bounds || agent->state.pos.z < min_z) {
            env->rewards[i] -= 1;
            env->terminals[i] = 1;
            add_log(env, i, true);
            reset_agent(env, agent, i);
        } else if (env->tick >= HORIZON - 1) {
            env->terminals[i] = 1;
            add_log(env, i, false);
        }
    }
    if (env->tick >= HORIZON - 1) {
        c_reset(env);
    }

    compute_observations(env);
}

void c_close_client(Client *client) {
    CloseWindow();
    free(client);
}

void c_close(DronePP *env) {
    if (env->client != NULL) {
        c_close_client(env->client);
    }
}

static void update_camera_position(Client *c) {
    float r = c->camera_distance;
    float az = c->camera_azimuth;
    float el = c->camera_elevation;

    float x = r * cosf(el) * cosf(az);
    float y = r * cosf(el) * sinf(az);
    float z = r * sinf(el);

    c->camera.position = (Vector3){x, y, z};
    c->camera.target = (Vector3){0, 0, 0};
}

void handle_camera_controls(Client *client) {
    Vector2 mouse_pos = GetMousePosition();

    if (IsMouseButtonPressed(MOUSE_BUTTON_LEFT)) {
        client->is_dragging = true;
        client->last_mouse_pos = mouse_pos;
    }

    if (IsMouseButtonReleased(MOUSE_BUTTON_LEFT)) {
        client->is_dragging = false;
    }

    if (client->is_dragging && IsMouseButtonDown(MOUSE_BUTTON_LEFT)) {
        Vector2 mouse_delta = {mouse_pos.x - client->last_mouse_pos.x,
                               mouse_pos.y - client->last_mouse_pos.y};

        float sensitivity = 0.005f;

        client->camera_azimuth -= mouse_delta.x * sensitivity;

        client->camera_elevation += mouse_delta.y * sensitivity;
        client->camera_elevation =
            clampf(client->camera_elevation, -PI / 2.0f + 0.1f, PI / 2.0f - 0.1f);

        client->last_mouse_pos = mouse_pos;

        update_camera_position(client);
    }

    float wheel = GetMouseWheelMove();
    if (wheel != 0) {
        client->camera_distance -= wheel * 2.0f;
        client->camera_distance = clampf(client->camera_distance, 5.0f, 50.0f);
        update_camera_position(client);
    }
}

Client *make_client(DronePP *env) {
    Client *client = (Client *)calloc(1, sizeof(Client));

    client->width = WIDTH;
    client->height = HEIGHT;

    SetConfigFlags(FLAG_MSAA_4X_HINT); // antialiasing
    InitWindow(WIDTH, HEIGHT, "PufferLib DronePP");

#ifndef __EMSCRIPTEN__
    SetTargetFPS(60);
#endif

    if (!IsWindowReady()) {
        TraceLog(LOG_ERROR, "Window failed to initialize\n");
        free(client);
        return NULL;
    }

    client->camera_distance = 40.0f;
    client->camera_azimuth = 0.0f;
    client->camera_elevation = PI / 10.0f;
    client->is_dragging = false;
    client->last_mouse_pos = (Vector2){0.0f, 0.0f};

    client->camera.up = (Vector3){0.0f, 0.0f, 1.0f};
    client->camera.fovy = 45.0f;
    client->camera.projection = CAMERA_PERSPECTIVE;

    update_camera_position(client);

    // Initialize trail buffer
    client->trails = (Trail*)calloc(env->num_agents, sizeof(Trail));
    for (int i = 0; i < env->num_agents; i++) {
        Trail* trail = &client->trails[i];
        trail->index = 0;
        trail->count = 0;
        for (int j = 0; j < TRAIL_LENGTH; j++) {
            trail->pos[j] = env->agents[i].state.pos;
        }
    }

    return client;
}

const Color PUFF_RED = (Color){187, 0, 0, 255};
const Color PUFF_CYAN = (Color){0, 187, 187, 255};
const Color PUFF_WHITE = (Color){241, 241, 241, 241};
const Color PUFF_BACKGROUND = (Color){6, 24, 24, 255};

void DrawRing3D(Ring ring, float thickness, Color entryColor, Color exitColor) {
    float half_thick = thickness / 2.0f;

    Vector3 center_pos = {ring.pos.x, ring.pos.y, ring.pos.z};

    Vector3 entry_start_pos = {center_pos.x - half_thick * ring.normal.x,
                               center_pos.y - half_thick * ring.normal.y,
                               center_pos.z - half_thick * ring.normal.z};

    DrawCylinderWiresEx(entry_start_pos, center_pos, ring.radius, ring.radius, 32, entryColor);

    Vector3 exit_end_pos = {center_pos.x + half_thick * ring.normal.x,
                            center_pos.y + half_thick * ring.normal.y,
                            center_pos.z + half_thick * ring.normal.z};

    DrawCylinderWiresEx(center_pos, exit_end_pos, ring.radius, ring.radius, 32, exitColor);
}


void c_render(DronePP *env) {
    if (env->client == NULL) {
        env->client = make_client(env);
        if (env->client == NULL) {
            TraceLog(LOG_ERROR, "Failed to initialize client for rendering\n");
            return;
        }
    }
    env->render = true;
    env->grip_k_max = 1.0f;
    env->grip_k_min = 1.0f;
    env->box_k_max = 1.0f;
    env->box_k_min = 1.0f;
    env->box_k = 1.0f;
    if (WindowShouldClose()) {
        c_close(env);
        exit(0);
    }

    if (IsKeyDown(KEY_ESCAPE)) {
        c_close(env);
        exit(0);
    }

    if (IsKeyPressed(KEY_SPACE)) {
        env->task = (env->task + 1) % TASK_N;
        for (int i = 0; i < env->num_agents; i++) {
            set_target(env, i);
        }
        if (env->task == TASK_RACE) {
            float ring_radius = 2.0f;
            reset_rings(env->ring_buffer, env->max_rings, ring_radius);
        }
    }

    handle_camera_controls(env->client);

    Client *client = env->client;

    for (int i = 0; i < env->num_agents; i++) {
        Drone *agent = &env->agents[i];
        Trail *trail = &client->trails[i];
        trail->pos[trail->index] = agent->state.pos;
        trail->index = (trail->index + 1) % TRAIL_LENGTH;
        if (trail->count < TRAIL_LENGTH) {
            trail->count++;
        }
        if (env->terminals[i]) {
            trail->index = 0;
            trail->count = 0;
        }
    }

    BeginDrawing();
    ClearBackground(PUFF_BACKGROUND);

    BeginMode3D(client->camera);

    // draws bounding cube
    DrawCubeWires((Vector3){0.0f, 0.0f, 0.0f}, GRID_X * 2.0f,
        GRID_Y * 2.0f, GRID_Z * 2.0f, WHITE);

    for (int i = 0; i < env->num_agents; i++) {
        Drone *agent = &env->agents[i];

        // draws drone body
        DrawSphere((Vector3){agent->state.pos.x, agent->state.pos.y, agent->state.pos.z}, 0.3f, agent->color);

        // draws rotors according to thrust
        float T[4];
        for (int j = 0; j < 4; j++) {
            float rpm = (env->actions[4*i + j] + 1.0f) * 0.5f * agent->params.max_rpm;
            T[j] = agent->params.k_thrust * rpm * rpm;
        }

        const float rotor_radius = 0.15f;
        const float visual_arm_len = agent->params.arm_len * 4.0f;

        Vec3 rotor_offsets_body[4] = {{+visual_arm_len, 0.0f, 0.0f},
                                      {-visual_arm_len, 0.0f, 0.0f},
                                      {0.0f, +visual_arm_len, 0.0f},
                                      {0.0f, -visual_arm_len, 0.0f}};

        //Color base_colors[4] = {ORANGE, PURPLE, LIME, SKYBLUE};
        Color base_colors[4] = {agent->color, agent->color, agent->color, agent->color};

        for (int j = 0; j < 4; j++) {
            Vec3 world_off = quat_rotate(agent->state.quat, rotor_offsets_body[j]);

            Vector3 rotor_pos = {agent->state.pos.x + world_off.x, agent->state.pos.y + world_off.y,
                                 agent->state.pos.z + world_off.z};

            float rpm = (env->actions[4*i + j] + 1.0f) * 0.5f * agent->params.max_rpm;
            float intensity = 0.75f + 0.25f * (rpm / agent->params.max_rpm);

            Color rotor_color = (Color){(unsigned char)(base_colors[j].r * intensity),
                                        (unsigned char)(base_colors[j].g * intensity),
                                        (unsigned char)(base_colors[j].b * intensity), 255};

            DrawSphere(rotor_pos, rotor_radius, rotor_color);

            DrawCylinderEx((Vector3){agent->state.pos.x, agent->state.pos.y, agent->state.pos.z}, rotor_pos, 0.02f, 0.02f, 8,
                           BLACK);
        }

        // draws line with direction and magnitude of velocity / 10
        if (norm3(agent->state.vel) > 0.1f) {
            DrawLine3D((Vector3){agent->state.pos.x, agent->state.pos.y, agent->state.pos.z},
                       (Vector3){agent->state.pos.x + agent->state.vel.x * 0.1f, agent->state.pos.y + agent->state.vel.y * 0.1f,
                                 agent->state.pos.z + agent->state.vel.z * 0.1f},
                       MAGENTA);
        }

        // Draw trailing path
        Trail *trail = &client->trails[i];
        if (trail->count <= 2) {
            continue;
        }
        for (int j = 0; j < trail->count - 1; j++) {
            int idx0 = (trail->index - j - 1 + TRAIL_LENGTH) % TRAIL_LENGTH;
            int idx1 = (trail->index - j - 2 + TRAIL_LENGTH) % TRAIL_LENGTH;
            float alpha = (float)(TRAIL_LENGTH - j) / (float)trail->count * 0.8f; // fade out
            Color trail_color = ColorAlpha((Color){0, 187, 187, 255}, alpha);
            DrawLine3D((Vector3){trail->pos[idx0].x, trail->pos[idx0].y, trail->pos[idx0].z},
                       (Vector3){trail->pos[idx1].x, trail->pos[idx1].y, trail->pos[idx1].z},
                       trail_color);
        }

    }

    // Rings
    if (env->task == TASK_RACE) {
        float ring_thickness = 0.2f;
        for (int i = 0; i < env->max_rings; i++) {
            Ring ring = env->ring_buffer[i];
            DrawRing3D(ring, ring_thickness, GREEN, BLUE);
        }
    }

    if (env->task == TASK_PP2) {
        for (int i = 0; i < env->num_agents; i++) {
            Drone *agent = &env->agents[i];
            Vec3 render_pos = agent->box_pos;
            DrawCube((Vector3){render_pos.x, render_pos.y, render_pos.z}, agent->box_size, agent->box_size, agent->box_size, BROWN);
            DrawCube((Vector3){agent->drop_pos.x, agent->drop_pos.y, agent->drop_pos.z}, 0.5f, 0.5f, 0.1f, YELLOW);
            //DrawSphere((Vector3){agent->hidden_pos.x, agent->hidden_pos.y, agent->hidden_pos.z}, 0.05f, YELLOW);
        }
    }

    if (IsKeyDown(KEY_TAB)) {
        for (int i = 0; i < env->num_agents; i++) {
            Drone *agent = &env->agents[i];
            Vec3 target_pos = agent->target_pos;
            DrawSphere((Vector3){target_pos.x, target_pos.y, target_pos.z}, 0.45f, (Color){0, 255, 255, 100});
        }
    }

    EndMode3D();

    DrawText("Left click + drag: Rotate camera", 10, 10, 16, PUFF_WHITE);
    DrawText("Mouse wheel: Zoom in/out", 10, 30, 16, PUFF_WHITE);
    DrawText(TextFormat("Task: %s", TASK_NAMES[env->task]), 10, 50, 16, PUFF_WHITE);
    DrawText(TextFormat("K = %.3f", env->grip_k), 10, 70, 16, PUFF_WHITE);

    EndDrawing();
}
