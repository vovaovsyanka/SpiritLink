"""Начальная схема: users, auth_sessions, user_game_state, user_passes, attempts

Revision ID: 0001
Revises: 
Create Date: 2026-10-20 19:48:07.801977
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('users',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('login', sa.String(length=32), nullable=False),
    sa.Column('password_hash', sa.Text(), nullable=False),
    sa.Column('display_name', sa.String(length=64), nullable=False),
    sa.Column('role', sa.String(length=16), server_default='player', nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("login ~ '^[a-z0-9_.-]{3,32}$'", name=op.f('ck_users_login_format')),
    sa.CheckConstraint("role IN ('player', 'admin')", name=op.f('ck_users_role_valid')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_users')),
    sa.UniqueConstraint('login', name=op.f('uq_users_login'))
    )
    op.create_table('auth_sessions',
    sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('session_token_hash', sa.LargeBinary(length=32), nullable=False),
    sa.Column('user_agent', sa.String(length=512), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_auth_sessions_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_auth_sessions')),
    sa.UniqueConstraint('session_token_hash', name=op.f('uq_auth_sessions_session_token_hash'))
    )
    op.create_index(op.f('ix_auth_sessions_user_id'), 'auth_sessions', ['user_id'], unique=False)
    op.create_table('user_game_state',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('world_level', sa.SmallInteger(), server_default='2', nullable=False),
    sa.Column('current_pass_id', sa.String(length=32), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('world_level BETWEEN 1 AND 4', name=op.f('ck_user_game_state_world_level_range')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_user_game_state_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', name=op.f('pk_user_game_state'))
    )
    op.create_table('user_passes',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('pass_id', sa.String(length=32), nullable=False),
    sa.Column('phase', sa.String(length=16), server_default='investigation', nullable=False),
    sa.Column('collected_clues', postgresql.ARRAY(sa.Text()), server_default='{}', nullable=False),
    sa.Column('secret', sa.Text(), nullable=False),
    sa.Column('used_secrets', postgresql.ARRAY(sa.Text()), server_default='{}', nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("phase IN ('investigation', 'puzzle', 'free_prompt', 'done')", name=op.f('ck_user_passes_phase_valid')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_user_passes_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', 'pass_id', name=op.f('pk_user_passes'))
    )
    op.create_table('attempts',
    sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('pass_id', sa.String(length=32), nullable=True),
    sa.Column('prompt_text', sa.Text(), nullable=False),
    sa.Column('llm_response', sa.Text(), nullable=True),
    sa.Column('success', sa.Boolean(), nullable=False),
    sa.Column('classifier_output', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('world_level', sa.SmallInteger(), nullable=False),
    sa.Column('latency_ms', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id', 'pass_id'], ['user_passes.user_id', 'user_passes.pass_id'], name=op.f('fk_attempts_user_id_pass_id_user_passes'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_attempts_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_attempts'))
    )
    op.create_index('ix_attempts_user_created', 'attempts', ['user_id', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_attempts_user_created', table_name='attempts')
    op.drop_table('attempts')
    op.drop_table('user_passes')
    op.drop_table('user_game_state')
    op.drop_index(op.f('ix_auth_sessions_user_id'), table_name='auth_sessions')
    op.drop_table('auth_sessions')
    op.drop_table('users')
