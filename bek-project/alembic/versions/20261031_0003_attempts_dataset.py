"""Журнал попыток как набор данных для дообучения: вердикты BERT и шлюза, ответ модели, проверка утечки

Строки прежнего формата (трасса в classifier_output, отказы гигиены, ввод слова-якоря) в новый не переносятся:
в таблице были только отладочные данные разработки, поэтому она очищается.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-31 12:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0003'
down_revision: Union[str, None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('TRUNCATE TABLE attempts')
    op.drop_column('attempts', 'llm_response')
    op.drop_column('attempts', 'success')
    op.drop_column('attempts', 'classifier_output')
    op.alter_column('attempts', 'pass_id', existing_type=sa.String(length=32), nullable=False)

    op.add_column('attempts', sa.Column('bert_dangerous', sa.Boolean(), nullable=False))
    op.add_column('attempts', sa.Column('bert_probability', sa.REAL(), nullable=False))
    op.add_column('attempts', sa.Column('gate_model', sa.String(length=64), nullable=True))
    op.add_column('attempts', sa.Column('gate_topics', postgresql.ARRAY(sa.SmallInteger()), nullable=True))
    op.add_column('attempts', sa.Column('category_match', sa.Boolean(), nullable=True))
    op.add_column('attempts', sa.Column('reply_model', sa.String(length=64), nullable=True))
    op.add_column('attempts', sa.Column('model_response', sa.Text(), nullable=True))
    op.add_column('attempts', sa.Column('leaked', sa.Boolean(), nullable=True))
    op.add_column('attempts', sa.Column('leak_kind', sa.String(length=32), nullable=True))
    op.add_column('attempts', sa.Column('followed_by_password', sa.Boolean(), server_default=sa.text('false'), nullable=False))
    op.add_column('attempts', sa.Column('cache_hit', sa.Boolean(), server_default=sa.text('false'), nullable=False))


def downgrade() -> None:
    op.execute('TRUNCATE TABLE attempts')
    for column in ('cache_hit', 'followed_by_password', 'leak_kind', 'leaked', 'model_response', 'reply_model',
                   'category_match', 'gate_topics', 'gate_model', 'bert_probability', 'bert_dangerous'):
        op.drop_column('attempts', column)
    op.alter_column('attempts', 'pass_id', existing_type=sa.String(length=32), nullable=True)

    op.add_column('attempts', sa.Column('classifier_output', postgresql.JSONB(astext_type=sa.Text()), nullable=False))
    op.add_column('attempts', sa.Column('success', sa.Boolean(), nullable=False))
    op.add_column('attempts', sa.Column('llm_response', sa.Text(), nullable=True))
