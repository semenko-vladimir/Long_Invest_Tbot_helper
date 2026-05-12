"""drop_legacy_tables

Revision ID: 677b093fb5a9
Revises: 11b2d5cade18
Create Date: 2026-05-12 22:20:33.906253

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '677b093fb5a9'
down_revision: Union[str, Sequence[str], None] = '11b2d5cade18'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    _drop_table_if_exists('strategy_signals', ['ix_strategy_signals_id'])
    _drop_table_if_exists('strategy_settings', ['ix_strategy_settings_id'])
    _drop_table_if_exists('signal_tpsl', ['ix_signal_tpsl_id'])
    _drop_table_if_exists('signal_sma', ['ix_signal_sma_id'])
    _drop_table_if_exists('signal_rsi', ['ix_signal_rsi_id'])
    _drop_table_if_exists('signal_macd', ['ix_signal_macd_id'])
    _drop_table_if_exists('signal_gpt', ['ix_signal_gpt_id'])
    _drop_table_if_exists('signal_ema', ['ix_signal_ema_id'])
    _drop_table_if_exists('signal_bollinger', ['ix_signal_bollinger_id'])
    _drop_table_if_exists('signal_alligator', ['ix_signal_alligator_id'])


def _drop_table_if_exists(table_name: str, index_names: list[str]) -> None:
    inspector = sa.inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return

    existing_indexes = {index["name"] for index in inspector.get_indexes(table_name)}
    for index_name in index_names:
        if index_name in existing_indexes:
            op.drop_index(op.f(index_name), table_name=table_name)
    op.drop_table(table_name)


def downgrade() -> None:
    """Downgrade schema."""
    op.create_table('signal_alligator',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('jaw_period', sa.Integer(), nullable=True),
    sa.Column('jaw_shift', sa.Integer(), nullable=True),
    sa.Column('teeth_period', sa.Integer(), nullable=True),
    sa.Column('teeth_shift', sa.Integer(), nullable=True),
    sa.Column('lips_period', sa.Integer(), nullable=True),
    sa.Column('lips_shift', sa.Integer(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_signal_alligator_id'), 'signal_alligator', ['id'], unique=False)
    op.create_table('signal_bollinger',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('period', sa.Integer(), nullable=True),
    sa.Column('deviation', sa.Float(), nullable=True),
    sa.Column('type_ma', sa.String(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_signal_bollinger_id'), 'signal_bollinger', ['id'], unique=False)
    op.create_table('signal_ema',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('fastLength', sa.Integer(), nullable=True),
    sa.Column('slowLength', sa.Integer(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_signal_ema_id'), 'signal_ema', ['id'], unique=False)
    op.create_table('signal_gpt',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('text', sa.String(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_signal_gpt_id'), 'signal_gpt', ['id'], unique=False)
    op.create_table('signal_macd',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('fastLength', sa.Integer(), nullable=True),
    sa.Column('slowLength', sa.Integer(), nullable=True),
    sa.Column('signalLength', sa.Integer(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_signal_macd_id'), 'signal_macd', ['id'], unique=False)
    op.create_table('signal_rsi',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('period', sa.Float(), nullable=True),
    sa.Column('hightLevel', sa.Float(), nullable=True),
    sa.Column('lowLevel', sa.Float(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_signal_rsi_id'), 'signal_rsi', ['id'], unique=False)
    op.create_table('signal_sma',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('fastLength', sa.Integer(), nullable=True),
    sa.Column('slowLength', sa.Integer(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_signal_sma_id'), 'signal_sma', ['id'], unique=False)
    op.create_table('signal_tpsl',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('take_profit', sa.Float(), nullable=True),
    sa.Column('stop_loss', sa.Float(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_signal_tpsl_id'), 'signal_tpsl', ['id'], unique=False)
    op.create_table('strategy_settings',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('time', sa.String(), nullable=True),
    sa.Column('auto_market', sa.Boolean(), nullable=True),
    sa.Column('quantity', sa.Integer(), nullable=True),
    sa.Column('joint', sa.Boolean(), nullable=True),
    sa.Column('sandbox_trigger', sa.Boolean(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_strategy_settings_id'), 'strategy_settings', ['id'], unique=False)
    op.create_table('strategy_signals',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('tpls_trigger', sa.Boolean(), nullable=True),
    sa.Column('rsi_trigger', sa.Boolean(), nullable=True),
    sa.Column('sma_trigger', sa.Boolean(), nullable=True),
    sa.Column('ema_trigger', sa.Boolean(), nullable=True),
    sa.Column('alligator_trigger', sa.Boolean(), nullable=True),
    sa.Column('gpt_trigger', sa.Boolean(), nullable=True),
    sa.Column('lstm_trigger', sa.Boolean(), nullable=True),
    sa.Column('bollinger_trigger', sa.Boolean(), nullable=True),
    sa.Column('macd_trigger', sa.Boolean(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_strategy_signals_id'), 'strategy_signals', ['id'], unique=False)
