
from __future__ import division

import tensorflow as tf

class CaptionGenerator(object):
    def __init__(self, word_to_idx, dim_feature=[196, 512], dim_embed=512, dim_hidden=1024, dim_senti=512, n_time_step=16, beam_index=5,
                 prev2out=True, ctx2out=True, alpha_c=0.0, selector=True, dropout=True):

        self.word_to_idx = word_to_idx
        self.idx_to_word = {i: w for w, i in word_to_idx.iteritems()}
        self.prev2out = prev2out
        self.ctx2out = ctx2out
        self.alpha_c = alpha_c
        self.selector = selector
        self.dropout = dropout
        self.V = len(word_to_idx)
        self.L = dim_feature[0]
        self.D = dim_feature[1]
        self.M = dim_embed
        self.H = dim_hidden
        self.E = dim_senti
        self.T = n_time_step
        self.beam = beam_index
        self._start = word_to_idx['<START>']
        self._null = word_to_idx['<NULL>']
        self._end = word_to_idx['<END>']

        self.weight_initializer = tf.contrib.layers.xavier_initializer()
        self.const_initializer = tf.constant_initializer(0.0)
        self.emb_initializer = tf.random_uniform_initializer(minval=-0.5, maxval=0.5)
        self.target_senti_initializer = tf.random_uniform_initializer(minval=-0.5, maxval=0.5)

        # Place holder for features and captions
        self.features = tf.placeholder(tf.float32, [None, self.L, self.D])
        self.captions = tf.placeholder(tf.int32, [None, self.T + 1])

        # sentence concat <start>
        self.sample_caption = tf.placeholder(tf.int32, [None, self.T])
        self.nsample = tf.placeholder(tf.int32)

        # placeholder definition
        self.whole_samples = tf.placeholder( tf.int32, shape=[None, self.T - 4] )  # sequence of tokens generated by generator
        self.rewards = tf.placeholder( tf.float32, shape=[None, self.T-4] )  # get from rollout policy and discriminator
        self.mode_learning = tf.placeholder(tf.int32)
        self.mode_sampling = tf.placeholder(tf.int32)


    def recurrent_unit(self, x, context, c, h, reuse=False):#, params):
      with tf.variable_scope('lstm_internal', reuse=reuse):
        # Weights and Bias for input and hidden tensor
        self.Wi_1 = tf.get_variable('Wi_1', [self.M, self.E], initializer=self.weight_initializer)
        self.Wi_2 = tf.get_variable('Wi_2_ss', [self.E, self.E], initializer=self.weight_initializer)
        self.Wi_3 = tf.get_variable('Wi_3', [self.E, self.H], initializer=self.weight_initializer)

        self.Ci_1 = tf.get_variable('Ci_1', [2048, self.E], initializer=self.weight_initializer)
        self.Ci_2 = tf.get_variable('Ci_2_ss', [self.E, self.E], initializer=self.weight_initializer)
        self.Ci_3 = tf.get_variable('Ci_3', [self.E, self.H], initializer=self.weight_initializer)

        self.Ui = tf.get_variable('Ui', [self.H, self.H], initializer=self.weight_initializer)
        self.bi = tf.get_variable('bi', [self.H], initializer=self.const_initializer)



        self.Wf_1 = tf.get_variable('Wf_1', [self.M, self.E], initializer=self.weight_initializer)
        self.Wf_2 = tf.get_variable('Wf_2_ss', [self.E, self.E], initializer=self.weight_initializer)
        self.Wf_3 = tf.get_variable('Wf_3', [self.E, self.H], initializer=self.weight_initializer)

        self.Cf_1 = tf.get_variable('Cf_1', [2048, self.E], initializer=self.weight_initializer)
        self.Cf_2 = tf.get_variable('Cf_2_ss', [self.E, self.E], initializer=self.weight_initializer)
        self.Cf_3 = tf.get_variable('Cf_3', [self.E, self.H], initializer=self.weight_initializer)

        self.Uf = tf.get_variable('Uf', [self.H, self.H], initializer=self.weight_initializer)
        self.bf = tf.get_variable('bf', [self.H], initializer=self.const_initializer)



        self.Wog_1 = tf.get_variable('Wog_1', [self.M, self.E], initializer=self.weight_initializer)
        self.Wog_2 = tf.get_variable('Wog_2_ss', [self.E, self.E], initializer=self.weight_initializer)
        self.Wog_3 = tf.get_variable('Wog_3', [self.E, self.H], initializer=self.weight_initializer)

        self.Cog_1 = tf.get_variable('Cog_1', [2048, self.E], initializer=self.weight_initializer)
        self.Cog_2 = tf.get_variable('Cog_2_ss', [self.E, self.E], initializer=self.weight_initializer)
        self.Cog_3 = tf.get_variable('Cog_3', [self.E, self.H], initializer=self.weight_initializer)

        self.Uog = tf.get_variable('Uog', [self.H, self.H], initializer=self.weight_initializer)
        self.bog = tf.get_variable('bog', [self.H], initializer=self.const_initializer)



        self.Wc_1 = tf.get_variable('Wc_1', [self.M, self.E], initializer=self.weight_initializer)
        self.Wc_2 = tf.get_variable('Wc_2_ss', [self.E, self.E], initializer=self.weight_initializer)
        self.Wc_3 = tf.get_variable('Wc_3', [self.E, self.H], initializer=self.weight_initializer)

        self.Cc_1 = tf.get_variable('Cc_1', [2048, self.E], initializer=self.weight_initializer)
        self.Cc_2 = tf.get_variable('Cc_2_ss', [self.E, self.E], initializer=self.weight_initializer)
        self.Cc_3 = tf.get_variable('Cc_3', [self.E, self.H], initializer=self.weight_initializer)

        self.Uc = tf.get_variable('Uc', [self.H, self.H], initializer=self.weight_initializer)
        self.bc = tf.get_variable('bc', [self.H], initializer=self.const_initializer)

        previous_hidden_state = h
        c_prev = c

        # Input Gate
        i = tf.sigmoid(
            tf.matmul( tf.matmul(tf.matmul(x, self.Wi_1) , self.Wi_2),  self.Wi_3)  + tf.matmul(tf.matmul(tf.matmul(context, self.Ci_1), self.Ci_2), self.Ci_3) +
            tf.matmul(previous_hidden_state, self.Ui) + self.bi
        )

        # Forget Gate
        f = tf.sigmoid(
            tf.matmul(tf.matmul(tf.matmul(x, self.Wf_1), self.Wf_2), self.Wf_3) + tf.matmul(
                tf.matmul(tf.matmul(context, self.Cf_1), self.Cf_2), self.Cf_3) +
            tf.matmul(previous_hidden_state, self.Uf) + self.bf
        )

        # Output Gate
        o = tf.sigmoid(
            tf.matmul(tf.matmul(tf.matmul(x, self.Wog_1), self.Wog_2), self.Wog_3) + tf.matmul(
                tf.matmul(tf.matmul(context, self.Cog_1), self.Cog_2), self.Cog_3) +
            tf.matmul(previous_hidden_state, self.Uog) + self.bog
        )

        # New Memory Cell
        c_ = tf.nn.tanh(
            tf.matmul(tf.matmul(tf.matmul(x, self.Wc_1), self.Wc_2), self.Wc_3) + tf.matmul(
                tf.matmul(tf.matmul(context, self.Cc_1), self.Cc_2), self.Cc_3) +
            tf.matmul(previous_hidden_state, self.Uc) + self.bc
        )

        # Final Memory cell
        c = f * c_prev + i * c_

        # Current Hidden state
        current_hidden_state = o * tf.nn.tanh(c)

        return (c, current_hidden_state)


    def _get_initial_lstm(self, features):
        with tf.variable_scope('initial_lstm'):

            features_mean = tf.reduce_mean(features, 1)

            w_h = tf.get_variable('w_h', [2048, self.H], initializer=self.weight_initializer)
            b_h = tf.get_variable('b_h', [self.H], initializer=self.const_initializer)
            h = tf.nn.tanh(tf.matmul(features_mean, w_h) + b_h)

            w_c = tf.get_variable('w_c', [2048, self.H], initializer=self.weight_initializer)
            b_c = tf.get_variable('b_c', [self.H], initializer=self.const_initializer)
            c = tf.nn.tanh(tf.matmul(features_mean, w_c) + b_c)

            return c, h

    def _word_embedding(self, inputs, reuse=False):
        with tf.variable_scope('word_embedding', reuse=reuse):
            w = tf.get_variable('w', [self.V, self.M], initializer=self.emb_initializer)
            x = tf.nn.embedding_lookup(w, inputs, name='word_vector')  # (N, T, M) or (N, M)
            return x

    def _target_senti_embedding(self, inputs, reuse=False):
        with tf.variable_scope('target_senti_embedding', reuse=reuse):
            w = tf.get_variable('w', [3, 256], initializer=self.target_senti_initializer, trainable=False)
            x = tf.nn.embedding_lookup(w, inputs, name='target_senti_vector')  # (N, T, M) or (N, M)
            x = x[:,0,:]
            return x

    def _imem_embedding(self, inputs, reuse=False):
        with tf.variable_scope('imem_embedding', reuse=reuse):
            w = tf.get_variable('w', [3, self.H], initializer=self.target_senti_initializer, trainable=False)
            x = tf.nn.embedding_lookup(w, inputs, name='target_senti_vector')  # (N, T, M) or (N, M)
            x = x[:,0,:]
            return x

    def _ext_embedding(self, inputs, reuse=False):
        with tf.variable_scope('ext_embedding', reuse=reuse):
            w = tf.get_variable('w', [3, 256], initializer=self.target_senti_initializer, trainable=False)
            x = tf.nn.embedding_lookup(w, inputs, name='ext_vector')  # (N, T, M) or (N, M)
            x = x[:,0,:]
            return x

    def _project_features(self, features):
        with tf.variable_scope('project_features'):
            w = tf.get_variable('w', [2048, 2048], initializer=self.weight_initializer)
            features_flat = tf.reshape(features, [-1, 2048])
            features_proj = tf.matmul(features_flat, w)
            features_proj = tf.reshape(features_proj, [-1, self.L, 2048])
            return features_proj

    def _attention_layer(self, features, features_proj, h, reuse=False):
        with tf.variable_scope('attention_layer', reuse=reuse):
            w = tf.get_variable('w', [self.H, 2048], initializer=self.weight_initializer)
            b = tf.get_variable('b', [2048], initializer=self.const_initializer)
            w_att = tf.get_variable('w_att', [2048, 1], initializer=self.weight_initializer)

            h_att = tf.nn.relu(features_proj + tf.expand_dims(tf.matmul(h, w), 1) + b)  # (N, L, D)
            out_att = tf.reshape(tf.matmul(tf.reshape(h_att, [-1, 2048]), w_att), [-1, self.L])  # (N, L)
            alpha = tf.nn.softmax(out_att)
            context = tf.reduce_sum(features * tf.expand_dims(alpha, 2), 1, name='context')  # (N, D)
            return context, alpha

    def _selector(self, context, h, reuse=False):
        with tf.variable_scope('selector', reuse=reuse):
            w = tf.get_variable('w', [self.H, 1], initializer=self.weight_initializer)
            b = tf.get_variable('b', [1], initializer=self.const_initializer)
            beta = tf.nn.sigmoid(tf.matmul(h, w) + b, 'beta')  # (N, 1)
            context = tf.multiply(beta, context, name='selected_context')
            return context, beta

    def _decode_lstm(self, x, h, context, features_target_senti, dropout=False, reuse=False):
        with tf.variable_scope('logits', reuse=reuse):

            w_h_1 = tf.get_variable('w_h_1', [self.H, self.E], initializer=self.weight_initializer)
            w_h_2 = tf.get_variable('w_h_2', [self.E, self.E], initializer=self.weight_initializer)
            w_h_3 = tf.get_variable('w_h_3', [self.E, self.M], initializer=self.weight_initializer)

            b_h = tf.get_variable('b_h', [self.M], initializer=self.const_initializer)

            w_out_1 = tf.get_variable('w_out_1', [self.M, self.E], initializer=self.weight_initializer)
            w_out_2 = tf.get_variable('w_out_2', [self.E, self.E], initializer=self.weight_initializer)
            w_out_3 = tf.get_variable('w_out_3', [self.E, self.V], initializer=self.weight_initializer)

            b_out = tf.get_variable('b_out', [self.V], initializer=self.const_initializer)

            if dropout:
                h = tf.nn.dropout(h, 0.5)
            h_logits = tf.matmul(tf.matmul(tf.matmul(h, w_h_1), w_h_2), w_h_3) + b_h

            if self.ctx2out:
                w_ctx2out_1 = tf.get_variable('w_ctx2out_1', [2048, self.E], initializer=self.weight_initializer)
                w_ctx2out_2 = tf.get_variable('w_ctx2out_2', [self.E, self.E], initializer=self.weight_initializer)
                w_ctx2out_3 = tf.get_variable('w_ctx2out_3', [self.E, self.M], initializer=self.weight_initializer)
                h_logits += tf.matmul(tf.matmul(tf.matmul(context, w_ctx2out_1), w_ctx2out_2), w_ctx2out_3)

            h_logits = tf.nn.tanh(h_logits)

            if dropout:
                h_logits = tf.nn.dropout(h_logits, 0.5)

            out_logits = tf.matmul(tf.matmul(tf.matmul(h_logits, w_out_1), w_out_2), w_out_3)

            w_ctx2out_extra = tf.get_variable('w_ctx2out_extra', [3, self.V], initializer=self.weight_initializer)
            out_logits += 0.0 * tf.matmul(features_target_senti, w_ctx2out_extra) + b_out

            return out_logits

    def _decode_lstm_2(self, x, h, context, features_target_senti, dropout=False, reuse=False):
        with tf.variable_scope('logits_2', reuse=reuse):
            w_h = tf.get_variable('w_h', [self.H, 512], initializer=self.weight_initializer)#, regularizer=tf.contrib.layers.l2_regularizer(0.01))
            b_h = tf.get_variable('b_h', [512], initializer=self.const_initializer)

            w_out = tf.get_variable('w_out', [512, 3], initializer=self.weight_initializer)#, regularizer=tf.contrib.layers.l2_regularizer(0.01))
            b_out = tf.get_variable('b_out', [3], initializer=self.const_initializer)

            h_logits = tf.matmul(h, w_h) + b_h
            h_logits = tf.nn.tanh(h_logits)

            out_logits = tf.matmul(h_logits, w_out) + b_out
            return out_logits

    def _batch_norm(self, x, mode='train', name=None):
        return tf.contrib.layers.batch_norm(inputs=x,
                                            decay=0.95,
                                            center=True,
                                            scale=True,
                                            is_training=(mode == 'train'),
                                            updates_collections=None,
                                            scope=(name + 'batch_norm'))

    def build_model(self):

        mode = self.mode_learning
        features = self.features
        captions = self.captions
        batch_size = tf.shape(features)[0]

        captions_in = captions[:, 4:self.T]
        captions_out = captions[:, 5:]
        mask = tf.to_float(tf.not_equal(captions_out, self._null))

        target_senti_label = tf.cast(self.captions[:, 0:3], tf.float32)

        features = self._batch_norm(features[:, :, 0:2048], mode='train', name='conv_features')

        c, h = self._get_initial_lstm(features=features)

        x = self._word_embedding(inputs=captions_in)

        x_samples = self._word_embedding(inputs=self.whole_samples, reuse=True)

        features_proj = self._project_features(features=features)

        loss = 0.0
        loss_2 = 0.0
        alpha_list = []
        sampled_word_list = []

        for t in range(self.T-4):
            context, alpha = self._attention_layer( features, features_proj, h, reuse=(t != 0) )
            alpha_list.append(alpha)

            if self.selector:
                context, beta = self._selector( context, h, reuse=(t != 0) )

            context = tf.nn.dropout(context, 0.5)


            x_temp = x[:, t, :]

            (c, h) = self.recurrent_unit(x_temp, context, c, h, reuse=(t != 0))

            logits = self._decode_lstm(x_temp, h, context, target_senti_label, dropout=self.dropout,reuse=(t != 0))

            loss += tf.reduce_sum( tf.nn.sparse_softmax_cross_entropy_with_logits(logits=logits,
                                                                   labels=captions_out[:, t]) * mask[:,t] )

            sampled_word_list.append(logits)

            logits_2 = self._decode_lstm_2(x[:,t,:], h, context, target_senti_label, dropout=self.dropout, reuse=(t!=0))
            loss_2 += tf.reduce_sum(tf.nn.sparse_softmax_cross_entropy_with_logits(logits = logits_2, labels=tf.argmax(tf.cast(target_senti_label, dtype=tf.int32),1) ))

        loss_2 = loss_2/(self.T-4)
        loss += 0.0*loss_2

        if self.alpha_c > 0:
            alphas = tf.transpose(tf.stack(alpha_list), (1, 0, 2))  # (N, T, L)
            alphas_all = tf.reduce_sum(alphas, 1)  # (N, L)
            alpha_reg = self.alpha_c * tf.reduce_sum((16. / 196 - alphas_all) ** 2)
            loss += alpha_reg

        loss= tf.cond(mode<2, lambda: loss / tf.to_float(batch_size), lambda: (loss / tf.to_float(batch_size)) + 0.01*tf.reduce_sum(tf.reduce_sum(tf.one_hot(tf.to_int32(tf.reshape(self.whole_samples, [-1])), self.V, 1.0, 0.0), 1) * tf.reshape(self.rewards, [-1]))/tf.to_float(batch_size) )

        return loss

    def build_sampler(self, max_len=20):

        features = self.features

        target_senti_label = tf.cast(features[:, 1, 2048:2051], tf.float32)

        features = self._batch_norm(features[:, :, 0:2048], mode='test', name='conv_features')

        c, h = self._get_initial_lstm(features=features)
        features_proj = self._project_features(features=features)

        sampled_word_list = []
        alpha_list = []
        beta_list = []

        sampled_word = self._start

        for t in range(max_len):

            if sampled_word == self._end:
                break

            if t == 0:
                x = self._word_embedding(inputs=tf.fill([tf.shape(features)[0]], self._start))
            else:
                x = self._word_embedding(inputs=sampled_word, reuse=True)

            context, alpha = self._attention_layer(features, features_proj, h, reuse=(t != 0))
            alpha_list.append(alpha)

            if self.selector:
                context, beta = self._selector(context, h, reuse=(t != 0))
                beta_list.append(beta)

            (c, h) = self.recurrent_unit(x, context, c, h, reuse=(t!=0) )

            logits= self._decode_lstm(x, h, context, target_senti_label, reuse=(t!= 0) )

            sampled_word = tf.argmax(logits, 1)
            sampled_word_list.append(sampled_word)

        alphas = tf.transpose(tf.stack(alpha_list), (1, 0, 2))
        betas = tf.transpose(tf.squeeze(beta_list), (1, 0))

        sampled_captions = tf.transpose(tf.stack(sampled_word_list), (1, 0))  # (N, max_len)

        return alphas, betas, sampled_captions


    def build_loss(self):

        features = self.features

        features_category = tf.cast(self.sample_caption[:, 3:4], tf.int32)
        features_target_senti = self._target_senti_embedding(inputs=features_category)
        features_ext = self._ext_embedding(inputs=features_category)

        captions = self.sample_caption[:, 4:self.T]
        mask = tf.to_float(tf.not_equal(captions, self._null))

        features = self._batch_norm(features[:, :, 0:512], mode='test', name='conv_features')

        c, h = self._get_initial_lstm(features=features)
        x = self._word_embedding(inputs=captions)
        features_proj = self._project_features(features=features)

        loss = []
        alpha_list = []
        lstm_cell = tf.nn.rnn_cell.BasicLSTMCell(num_units=self.H)

        for t in range(self.T-4):
            if t == 0:
                word = self._word_embedding(inputs=tf.fill([tf.shape(features)[0]], self._start))
            else:
                word= x[:, t -1, :]

            context, alpha = self._attention_layer(features, features_proj, h, reuse=(t != 0))
            alpha_list.append(alpha)

            if self.selector:
                context, beta = self._selector(context, h, reuse=(t != 0))

            context = tf.nn.dropout(context, 0.5)
            features_target_senti = tf.nn.dropout(features_target_senti, 0.5)
            features_ext = tf.nn.dropout(features_ext, 0.5)

            context_lstm = tf.concat([features_target_senti, context], 1)

            with tf.variable_scope('lstm', reuse=(t != 0)):
                _, (c, h) = lstm_cell(inputs=tf.concat([word, context_lstm], 1), state=[c, h])

            logits = self._decode_lstm(word, h, context_lstm, features_ext, reuse=(t != 0))
            # logits = tf.einsum('a,ac->ac', tf.to_float(lo#ss_weights), logits)

            softmax = tf.nn.softmax(logits, dim=-1, name=None)

            loss.append( tf.transpose(tf.multiply(tf.transpose(tf.log(tf.clip_by_value(softmax, 1e-20, 1.0)) * tf.one_hot(captions[:, t], self.V), [1, 0]),  mask[:, t]), [1, 0]))

        loss_out = tf.transpose(tf.stack(loss), (1, 0, 2))  # (N, T, max_len)

        return loss_out


    def build_multinomial_sampler(self, max_len=16):
        features = self.features

        features_category = tf.cast(features[:, 1, 515:516], tf.int32)
        features_target_senti = self._target_senti_embedding(inputs=features_category )
        features_ext = self._ext_embedding(inputs=features_category)

        features = self._batch_norm(features[:, :, 0:512], mode='test', name='conv_features')

        c, h = self._get_initial_lstm(features=features)
        features_proj = self._project_features(features=features)

        sampled_word_list = []
        alpha_list = []
        beta_list = []
        lstm_cell = tf.nn.rnn_cell.BasicLSTMCell(num_units=self.H)
        loss = []
        for t in range(self.T-4):
            if t == 0:
                x = self._word_embedding(inputs=tf.fill([tf.shape(features)[0]], self._start))
            else:
                x = self._word_embedding(inputs=sampled_word, reuse=True)

            context, alpha = self._attention_layer(features, features_proj, h, reuse=(t != 0))
            alpha_list.append(alpha)

            if self.selector:
                context, beta = self._selector(context, h, reuse=(t != 0))
                beta_list.append(beta)

            context = tf.nn.dropout(context, 0.5)
            features_target_senti = tf.nn.dropout(features_target_senti, 0.5)
            features_ext = tf.nn.dropout(features_ext, 0.5)

            context_lstm = tf.concat([features_target_senti, context], 1)

            with tf.variable_scope('lstm', reuse=(t != 0)):
                _, (c, h) = lstm_cell(inputs=tf.concat([x, context_lstm], 1), state=[c, h])

            logits = self._decode_lstm(x, h, context_lstm, features_ext, reuse=(t != 0))
            softmax = tf.nn.softmax(logits, dim=-1, name=None)
            sampled_word = tf.multinomial(tf.log(tf.clip_by_value(softmax, 1e-20, 1.0)), 1)

            sampled_word = tf.reshape(sampled_word, [-1])
            loss.append(tf.log(tf.clip_by_value(softmax, 1e-20, 1.0)) * tf.one_hot(tf.identity(sampled_word), self.V))

            sampled_word_list.append(sampled_word)

        alphas = tf.transpose(tf.stack(alpha_list), (1, 0, 2))
        betas = tf.transpose(tf.squeeze(beta_list), (1, 0))
        loss_out = tf.transpose(tf.stack(loss), (1, 0, 2))
        sampled_captions = tf.transpose(tf.stack(sampled_word_list), (1, 0))
        return alphas, betas, sampled_captions,loss_out